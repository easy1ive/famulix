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
    items = gather_memories(graph, now_s=now_s, budget_tokens=budget_tokens)

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
        scores = score_all_nodes(graph, now_s=int(briefing.metadata.get("generated_at_s", "0")))
        hourly = [0.0] * 24
        daily: dict[str, list[float]] = {}
        from datetime import datetime, timedelta, timezone

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

    return render_htm(
        briefing.title,
        report_sections,
        metadata=briefing.metadata,
        svg_charts=svg_charts,
    )


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
