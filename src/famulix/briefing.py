"""Daily briefing application — the flagship offline app.

Pipeline: gather → select → compose → cite. Produces a self-contained
HTML + SVG briefing where every item cites the memory ids it used.
Includes agenda, commitments, reminders, and recent memory sections.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from famulix.connectors import ConnectorHub
from famulix.consolidation import consolidate_graph
from famulix.context import ContextItem, assemble_context, estimate_tokens
from famulix.encoding import encode_events_to_graph
from famulix.memory_graph import MemoryGraph
from famulix.reports import (
    ReportSection,
    run_metadata,
    svg_commitment_timeline,
    svg_day_ribbon,
    svg_heatmap,
)
from famulix.retrieval import BM25Index, hybrid_score
from famulix.salience import score_all_nodes


@dataclass
class BriefingItem:
    """A single item in the briefing with citation."""

    title: str
    body: str
    section: str
    memory_ids: list[str] = field(default_factory=list)
    priority: float = 0.5

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "body": self.body,
            "section": self.section,
            "memory_ids": list(self.memory_ids),
            "priority": round(self.priority, 6),
        }


@dataclass
class Briefing:
    """A complete daily briefing."""

    title: str
    date_str: str
    items: list[BriefingItem] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)

    def all_cited_memory_ids(self) -> set[str]:
        ids: set[str] = set()
        for item in self.items:
            ids.update(item.memory_ids)
        return ids

    @property
    def citation_count(self) -> int:
        return len(self.all_cited_memory_ids())

    @property
    def item_count(self) -> int:
        return len(self.items)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "title": self.title,
            "date_str": self.date_str,
            "item_count": self.item_count,
            "citation_count": self.citation_count,
            "sections": list(self.sections),
            "section_counts": self.section_counts(),
            "items": [item.to_dict() for item in self.items],
            "metadata": dict(self.metadata),
            "limitations": list(self.limitations),
        }

    def section_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.section] = counts.get(item.section, 0) + 1
        return counts

    def citations_resolve(self, graph: MemoryGraph) -> bool:
        """Check that all cited memory ids point to existing, non-deleted nodes."""
        for mid in self.all_cited_memory_ids():
            node = graph.get_node(mid)
            if node is None:
                return False
            if not node.is_active:
                return False
            if node.metadata.get("deleted") == "true":
                return False
        return True


DEFAULT_SECTION_ORDER: tuple[str, ...] = ("agenda", "commitments", "reminders", "recent_memories")


def sort_items_by_section(
    items: list[BriefingItem],
    section_order: tuple[str, ...] = DEFAULT_SECTION_ORDER,
) -> list[BriefingItem]:
    """Reorder briefing items by section according to a custom order.

    Items in sections not listed in section_order appear at the end in their
    original relative order. Items within the same section retain their
    original ordering.
    """
    order_map = {section: index for index, section in enumerate(section_order)}
    max_order = len(section_order)

    def sort_key(item: BriefingItem) -> tuple[int, int]:
        section_rank = order_map.get(item.section, max_order)
        return (section_rank, items.index(item))

    return sorted(items, key=sort_key)


def _build_index(graph: MemoryGraph) -> BM25Index:
    idx = BM25Index()
    for node in graph.all_nodes():
        if node.is_active and node.kind in {"fact", "episode", "reminder", "goal"}:
            idx.add_node(node)
    return idx


def gather_memories(
    graph: MemoryGraph,
    *,
    now_s: int,
    budget_tokens: int = 500,
) -> list[BriefingItem]:
    """Gather and select memories for the briefing within a token budget."""
    idx = _build_index(graph)
    results = hybrid_score(
        "today agenda commitments reminders",
        graph=graph,
        index=idx,
        now_s=now_s,
    )

    # Convert to context items
    context_items: list[ContextItem] = []
    for r in results[:30]:
        node = graph.get_node(r.node_id)
        if node is None:
            continue
        text = f"{node.title}: {node.body}"
        context_items.append(
            ContextItem(
                item_id=node.node_id,
                token_estimate=estimate_tokens(text),
                value=r.score,
                payload=text,
            )
        )

    assembled = assemble_context(context_items, budget=budget_tokens)
    items: list[BriefingItem] = []
    for ci in assembled.items:
        node = graph.get_node(ci.item_id)
        if node is None:
            continue
        section = "recent_memories"
        if node.kind == "reminder":
            section = "reminders"
        elif node.kind == "goal":
            section = "commitments"
        items.append(
            BriefingItem(
                title=node.title,
                body=node.body,
                section=section,
                memory_ids=[node.node_id],
                priority=ci.value,
            )
        )
    return items


def _section_order(section: str) -> int:
    order = {"agenda": 0, "commitments": 1, "reminders": 2, "recent_memories": 3}
    return order.get(section, 99)


def build_commitments_section(
    graph: MemoryGraph,
    *,
    now_s: int,
    horizon_s: int = 86400 * 14,
) -> list[BriefingItem]:
    """Extract goal and commitment nodes within a lookahead horizon."""
    items: list[BriefingItem] = []
    for node in graph.all_nodes():
        if not node.is_active or node.kind != "goal":
            continue
        due = node.metadata.get("due_at_s")
        if due is None:
            priority = 0.4
        else:
            remaining = int(due) - now_s
            if remaining < 0:
                priority = 0.9  # overdue
            elif remaining <= horizon_s:
                priority = 0.5 + 0.4 * (1 - remaining / max(horizon_s, 1))
            else:
                continue  # beyond horizon, skip
        items.append(
            BriefingItem(
                title=node.title,
                body=node.body,
                section="commitments",
                memory_ids=[node.node_id],
                priority=round(priority, 6),
            )
        )
    items.sort(key=lambda it: -it.priority)
    return items


def build_agenda_section(
    graph: MemoryGraph,
    *,
    day_start_s: int,
    day_end_s: int,
) -> list[BriefingItem]:
    """Extract calendar and time-bound memories for the day's agenda."""
    items: list[BriefingItem] = []
    for node in graph.all_nodes():
        if not node.is_active:
            continue
        created = node.created_at_s
        if not (day_start_s <= created < day_end_s):
            continue
        if node.kind == "episode" and node.metadata.get("event_types", "").count("calendar") > 0:
            items.append(
                BriefingItem(
                    title=node.title,
                    body=node.body,
                    section="agenda",
                    memory_ids=[node.node_id],
                    priority=0.7,
                )
            )
        elif node.kind == "reminder":
            due = node.metadata.get("due_at_s")
            if due is not None and day_start_s <= int(due) < day_end_s:
                items.append(
                    BriefingItem(
                        title=f"Reminder: {node.title}",
                        body=node.body,
                        section="agenda",
                        memory_ids=[node.node_id],
                        priority=0.8,
                    )
                )
    items.sort(key=lambda it: -it.priority)
    return items


def build_reminders_section(
    graph: MemoryGraph,
    *,
    now_s: int,
    lookahead_s: int = 86400 * 3,
) -> list[BriefingItem]:
    """Extract active reminders within a lookahead window."""
    items: list[BriefingItem] = []
    for node in graph.all_nodes():
        if not node.is_active or node.kind != "reminder":
            continue
        due = node.metadata.get("due_at_s")
        if due is None:
            continue
        due_s = int(due)
        remaining = due_s - now_s
        if remaining < 0:
            priority = 0.95  # overdue
        elif remaining <= lookahead_s:
            priority = 0.5 + 0.4 * (1 - remaining / max(lookahead_s, 1))
        else:
            continue
        items.append(
            BriefingItem(
                title=node.title,
                body=node.body,
                section="reminders",
                memory_ids=[node.node_id],
                priority=round(priority, 6),
            )
        )
    items.sort(key=lambda it: -it.priority)
    return items


def dedupe_briefing_items(items: list[BriefingItem]) -> list[BriefingItem]:
    """Keep the first item per cited memory across already-ordered sections.

    Sections are concatenated in priority order, so the first occurrence of a
    memory wins. Items that cite nothing get a positional key, which keeps
    them all and keeps the result independent of object identity.
    """
    seen: set[str] = set()
    kept: list[BriefingItem] = []
    for position, item in enumerate(items):
        key = item.memory_ids[0] if item.memory_ids else f"#unreferenced:{position}"
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept


def build_briefing(
    graph: MemoryGraph,
    *,
    date_str: str,
    now_s: int,
    budget_tokens: int = 500,
    version: str = "0.1.0",
    seed: int = 0,
    config_hash: str = "",
    extra_limitations: list[str] | None = None,
) -> Briefing:
    """Build a complete daily briefing."""
    day_start = now_s - (now_s % 86400)
    agenda_items = build_agenda_section(
        graph,
        day_start_s=day_start,
        day_end_s=day_start + 86400,
    )
    commitment_items = build_commitments_section(graph, now_s=now_s)
    reminder_items = build_reminders_section(graph, now_s=now_s)
    memory_items = gather_memories(graph, now_s=now_s, budget_tokens=budget_tokens)

    combined = agenda_items + commitment_items + reminder_items + memory_items
    items = dedupe_briefing_items(combined)

    # Group by section
    section_names = sorted({it.section for it in items}, key=_section_order)

    # Sort items by section order then priority
    items.sort(key=lambda it: (_section_order(it.section), -it.priority))

    limitations = [
        "All content generated from synthetic memory data.",
        "No external model calls — deterministic rule-based pipeline.",
        "Scores reflect salience heuristics, not real relevance judgments.",
    ]
    if extra_limitations:
        limitations.extend(extra_limitations)

    meta = run_metadata(
        version=version,
        seed=seed,
        config_hash=config_hash,
        extra={"date": date_str, "budget_tokens": str(budget_tokens)},
    )

    return Briefing(
        title=f"Daily Briefing — {date_str}",
        date_str=date_str,
        items=items,
        sections=section_names,
        metadata=meta,
        limitations=limitations,
    )


def render_briefing_markdown(briefing: Briefing) -> str:
    """Render the briefing as Markdown."""
    from famulix.reports import render_markdown as render_md

    sections_by_name: dict[str, list[tuple[str, str]]] = {}
    for item in briefing.items:
        sections_by_name.setdefault(item.section, [])
        cites = ", ".join(item.memory_ids[:3])
        label = item.title
        value = f"{item.body} (cited: {cites})"
        sections_by_name[item.section].append((label, value))

    report_sections: list[ReportSection] = []
    for section_name in briefing.sections:
        items = sections_by_name.get(section_name, [])
        report_sections.append(ReportSection(title=section_name, items=items))

    # Add limitations section
    lim_items = [("limitation", lim) for lim in briefing.limitations]
    report_sections.append(ReportSection(title="limitations", items=lim_items))

    return render_md(briefing.title, report_sections, metadata=briefing.metadata)


def render_briefing_json(briefing: Briefing) -> str:
    """Render the briefing as a structured JSON string."""
    import json

    return json.dumps(briefing.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)


def render_briefing_html(
    briefing: Briefing,
    *,
    graph: MemoryGraph | None = None,
) -> str:
    """Render the briefing as self-contained HTML with SVG visuals."""
    from famulix.reports import render_html as render_htm

    sections_by_name: dict[str, list[tuple[str, str]]] = {}
    for item in briefing.items:
        sections_by_name.setdefault(item.section, [])
        cites = ", ".join(item.memory_ids[:3])
        sections_by_name[item.section].append((item.title, f"{item.body} [{cites}]"))

    report_sections: list[ReportSection] = []
    for section_name in briefing.sections:
        items = sections_by_name.get(section_name, [])
        report_sections.append(ReportSection(title=section_name, items=items))

    # Add limitations
    lim_items = [("limitation", lim) for lim in briefing.limitations]
    report_sections.append(ReportSection(title="limitations", items=lim_items))

    # SVG charts
    svg_charts: list[str] = []
    if graph is not None:
        from datetime import datetime, timedelta, timezone

        scores = score_all_nodes(graph, now_s=int(briefing.metadata.get("generated_at_s", "0")))
        hourly = [0.0] * 24
        daily: dict[str, list[float]] = {}

        for node in graph.all_nodes():
            if not node.is_active:
                continue
            local = datetime.fromtimestamp(node.created_at_s, tz=timezone(timedelta(hours=8)))
            day = local.date().isoformat()
            daily.setdefault(day, [0.0] * 24)[local.hour] += scores.get(node.node_id, 0.0)
            hourly[local.hour] += scores.get(node.node_id, 0.0)
        svg_charts.append(svg_day_ribbon(hourly))
        days = sorted(daily)[-7:]
        heat_data = [daily[day] for day in days]
        if heat_data:
            svg_charts.append(svg_heatmap(heat_data, title="Memory salience by local day and hour"))

        commitment_items = [it for it in briefing.items if it.section == "commitments"]
        if commitment_items:
            timeline_data: list[tuple[str, float, float]] = []
            for idx, item in enumerate(commitment_items[:5]):
                start_day = float(idx * 0.8)
                duration = max(0.5, float(item.priority) * 1.5)
                timeline_data.append((item.title[:20], start_day, duration))
            svg_charts.append(svg_commitment_timeline(timeline_data))

    return render_htm(
        briefing.title,
        report_sections,
        metadata=briefing.metadata,
        svg_charts=svg_charts,
    )


def estimate_briefing_tokens(briefing: Briefing) -> int:
    """Rough token estimate for the full briefing text content."""
    total = len(briefing.title.split())
    for item in briefing.items:
        total += len(item.title.split()) + len(item.body.split())
    return total


def truncate_briefing(briefing: Briefing, *, max_items: int) -> Briefing:
    """Return a copy of the briefing with at most max_items per section,
    preserving section order and highest-priority items first."""
    from dataclasses import replace

    per_section: dict[str, list[BriefingItem]] = {}
    for item in briefing.items:
        per_section.setdefault(item.section, []).append(item)

    kept: list[BriefingItem] = []
    for section_name in briefing.sections:
        section_items = per_section.get(section_name, [])
        section_items_sorted = sorted(section_items, key=lambda it: -it.priority)
        kept.extend(section_items_sorted[:max_items])

    active_sections = sorted({it.section for it in kept}, key=_section_order)
    return replace(briefing, items=kept, sections=active_sections)


def build_briefing_from_connectors(
    connectors: ConnectorHub,
    *,
    date_str: str,
    now_s: int,
    budget_tokens: int = 500,
    seed: int = 0,
) -> tuple[MemoryGraph, Briefing]:
    """Run local connector records through ingestion and cited briefing."""
    events = connectors.to_events()
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)
    briefing = build_briefing(
        graph,
        date_str=date_str,
        now_s=now_s,
        budget_tokens=budget_tokens,
        seed=seed,
    )
    if not briefing.citations_resolve(graph):
        raise RuntimeError("connector briefing contains an unresolved citation")
    return graph, briefing
