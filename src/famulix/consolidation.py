"""Memory consolidation: dedup, merge, contradiction resolution.

Strategies:
- Near-duplicate merging with stable winner selection.
- Template-based episode summaries with provenance.
- Contradiction detection (same fact key, incompatible values) with a
  deterministic supersede policy: newest-verified wins; ties broken by
  source trust then id.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from famulix.memory_graph import MemoryEdge, MemoryGraph, MemoryNode


@dataclass
class ConsolidationReport:
    """Auditable record of what a consolidation run changed."""

    merged_pairs: list[tuple[str, str]] = field(default_factory=list)
    superseded: list[str] = field(default_factory=list)
    contradictions_resolved: int = 0
    summary_nodes: list[str] = field(default_factory=list)

    def total_changes(self) -> int:
        return len(self.merged_pairs) + len(self.superseded) + len(self.summary_nodes)

    @property
    def is_empty(self) -> bool:
        return self.total_changes() == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "merged_pairs": list(self.merged_pairs),
            "superseded": list(self.superseded),
            "contradictions_resolved": self.contradictions_resolved,
            "summary_nodes": list(self.summary_nodes),
            "total_changes": self.total_changes(),
        }

    def to_markdown(self) -> str:
        """Render the report as deterministic Markdown.

        Output is stable for a given report state and escapes no special
        characters beyond what Markdown requires. Sections are omitted when
        empty so the format stays concise.
        """
        lines: list[str] = ["# Consolidation Report", ""]
        lines.append(f"**Total changes:** {self.total_changes()}")
        lines.append(f"**Contradictions resolved:** {self.contradictions_resolved}")
        lines.append("")

        if self.merged_pairs:
            lines.append("## Merged duplicates")
            lines.append("")
            for winner_id, loser_id in sorted(self.merged_pairs):
                lines.append(f"- `{winner_id}` ← `{loser_id}`")
            lines.append("")

        if self.superseded:
            lines.append("## Superseded facts")
            lines.append("")
            for node_id in sorted(self.superseded):
                lines.append(f"- `{node_id}`")
            lines.append("")

        if self.summary_nodes:
            lines.append("## Episode summaries")
            lines.append("")
            for node_id in sorted(self.summary_nodes):
                lines.append(f"- `{node_id}`")
            lines.append("")

        if self.is_empty:
            lines.append("No changes were made during this consolidation run.")
            lines.append("")

        return "\n".join(lines)


def _normalized_text(node: MemoryNode) -> str:
    text = f"{node.title} {node.body}".lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return round(SequenceMatcher(None, a, b).ratio(), 6)


def _canonical_pair(a: MemoryNode, b: MemoryNode) -> tuple[MemoryNode, MemoryNode]:
    """Order a pair by node id so results do not depend on traversal order."""
    return (a, b) if a.node_id <= b.node_id else (b, a)


def _max_partner_length(length: int, threshold: float) -> float:
    """Longest partner text that can still reach ``threshold`` similarity.

    ``SequenceMatcher.ratio()`` is ``2 * matches / (len(a) + len(b))`` and the
    matched span can never exceed the shorter text, so ``ratio`` is bounded by
    ``2 * min / (min + max)``. Solving that bound for ``max`` gives the length
    limit used to skip pairs that cannot possibly qualify.
    """
    if threshold <= 0.0:
        return float("inf")
    if threshold >= 2.0:
        return float(length)
    return length * (2.0 - threshold) / threshold


def _lengths_can_reach(len_a: int, len_b: int, threshold: float) -> bool:
    """Exact length prefilter: can these two lengths reach ``threshold``?"""
    low, high = (len_a, len_b) if len_a <= len_b else (len_b, len_a)
    return high <= _max_partner_length(low, threshold)


def _shared_char_count(counts_a: Counter[str], counts_b: Counter[str]) -> int:
    """Size of the multiset intersection of two character histograms."""
    small, large = (counts_a, counts_b) if len(counts_a) <= len(counts_b) else (counts_b, counts_a)
    shared = 0
    for char, count in small.items():
        other = large.get(char)
        if other is not None:
            shared += count if count < other else other
    return shared


def _chars_can_reach(
    counts_a: Counter[str], counts_b: Counter[str], total_length: int, threshold: float
) -> bool:
    """Exact character-multiset prefilter for a similarity threshold.

    ``ratio()`` equals ``2 * matches / total_length`` and the matched span can
    never contain more copies of a character than both texts hold, so the
    multiset intersection bounds it from above. Cheap to evaluate once per
    pair and far cheaper than running the sequence matcher.
    """
    if total_length <= 0:
        return False
    return 2 * _shared_char_count(counts_a, counts_b) >= threshold * total_length


def find_near_duplicates(
    graph: MemoryGraph,
    *,
    kind: str | None = None,
    threshold: float = 0.8,
) -> list[tuple[MemoryNode, MemoryNode, float]]:
    """Find pairs of nodes with text similarity above threshold.

    Returns list of (node_a, node_b, score) ordered by descending score, then
    by the pair's node ids. Pairs are canonicalised so the lower id comes
    first, which makes both the ordering and each score independent of graph
    insertion order.

    Texts are normalised once per node, and a pair is only diffed after two
    exact upper bounds — on length and on the character multiset — confirm it
    could still reach the threshold. Neither shortcut changes the result set.
    """
    candidates = [n for n in graph.all_nodes() if (kind is None or n.kind == kind) and n.is_active]
    texts = {n.node_id: _normalized_text(n) for n in candidates}
    counts = {node_id: Counter(text) for node_id, text in texts.items()}
    pairs: list[tuple[MemoryNode, MemoryNode, float]] = []
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            a, b = _canonical_pair(candidates[i], candidates[j])
            text_a, text_b = texts[a.node_id], texts[b.node_id]
            if not _lengths_can_reach(len(text_a), len(text_b), threshold):
                continue
            if not _chars_can_reach(
                counts[a.node_id], counts[b.node_id], len(text_a) + len(text_b), threshold
            ):
                continue
            score = _similarity(text_a, text_b)
            if score >= threshold:
                pairs.append((a, b, score))
    pairs.sort(key=lambda x: (-x[2], x[0].node_id, x[1].node_id))
    return pairs


def merge_duplicate(
    graph: MemoryGraph,
    survivor: MemoryNode,
    obsolete: MemoryNode,
) -> None:
    """Merge obsolete into survivor, redirecting edges.

    The obsolete node is marked inactive; its incoming/outgoing edges are
    reattached to the survivor. A 'derived_from' edge records the merge.
    """
    if not graph.has_node(survivor.node_id) or not graph.has_node(obsolete.node_id):
        raise ValueError("Both nodes must exist in the graph")

    # Reattach in-edges
    for e in list(graph.in_edges(obsolete.node_id)):
        new_edge = MemoryEdge.create(e.from_id, survivor.node_id, e.kind, e.weight)
        graph.add_edge(new_edge)

    # Reattach out-edges
    for e in list(graph.out_edges(obsolete.node_id)):
        new_edge = MemoryEdge.create(survivor.node_id, e.to_id, e.kind, e.weight)
        graph.add_edge(new_edge)

    # Mark obsolete as inactive by replacing with inactive version
    from dataclasses import replace

    inactive = replace(obsolete, is_active=False)
    graph._nodes[obsolete.node_id] = inactive  # noqa: SLF001

    # Record provenance: survivor derived_from obsolete
    graph.add_edge(MemoryEdge.create(survivor.node_id, obsolete.node_id, "derived_from"))
    graph.add_edge(MemoryEdge.create(survivor.node_id, obsolete.node_id, "supersedes"))


def _fact_key(node: MemoryNode) -> str:
    """Derive a fact key from a fact node.

    Uses the first 5 words of the title as a rough key for contradiction
    detection. Nodes sharing a key are candidates for contradiction checks.
    """
    words = re.findall(r"[\w]+", node.title.lower())
    return "_".join(words[:5])


def find_contradictions(
    graph: MemoryGraph,
) -> list[tuple[MemoryNode, MemoryNode]]:
    """Find pairs of active fact nodes that share a key but have different bodies.

    These are candidate contradictions; the supersede policy decides which
    version wins.
    """
    fact_nodes = [n for n in graph.all_nodes() if n.kind == "fact" and n.is_active]
    by_key: dict[str, list[MemoryNode]] = {}
    for n in fact_nodes:
        key = _fact_key(n)
        if key:
            by_key.setdefault(key, []).append(n)
    pairs: list[tuple[MemoryNode, MemoryNode]] = []
    for _key, nodes in by_key.items():
        if len(nodes) < 2:
            continue
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                if a.body != b.body:
                    pairs.append((a, b))
    return pairs


def resolve_contradiction(
    newer: MemoryNode,
    older: MemoryNode,
    *,
    newer_trusted: bool = True,
    older_trusted: bool = False,
) -> MemoryNode:
    """Deterministic supersede policy: newest-verified wins.

    Ties broken by source trust (trusted > untrusted) then node id (stable).
    Returns the winner.
    """
    # Newer wins if it's verified
    if newer_trusted and not older_trusted:
        return newer
    if older_trusted and not newer_trusted:
        return older
    # Both same trust: newer by timestamp wins
    if newer.created_at_s > older.created_at_s:
        return newer
    if older.created_at_s > newer.created_at_s:
        return older
    # Tie by id for absolute determinism
    return newer if newer.node_id >= older.node_id else older


def consolidate_graph(
    graph: MemoryGraph,
    *,
    dedup_threshold: float = 0.85,
) -> ConsolidationReport:
    """Run a full consolidation pass.

    1. Dedup near-duplicate fact nodes.
    2. Detect and resolve contradictions among fact nodes.
    3. (Skips summary generation for now — added separately.)
    """
    report = ConsolidationReport()

    # Step 1: dedup
    dup_pairs = find_near_duplicates(graph, kind="fact", threshold=dedup_threshold)
    seen: set[str] = set()
    for a, b, _score in dup_pairs:
        if a.node_id in seen or b.node_id in seen:
            continue
        # Keep the newer one as survivor
        survivor, obsolete = (a, b) if a.created_at_s >= b.created_at_s else (b, a)
        survivor_node = graph.get_node(survivor.node_id)
        obsolete_node = graph.get_node(obsolete.node_id)
        if survivor_node is None or obsolete_node is None:
            continue
        if not survivor_node.is_active or not obsolete_node.is_active:
            continue
        merge_duplicate(graph, survivor, obsolete)
        report.merged_pairs.append((survivor.node_id, obsolete.node_id))
        seen.add(obsolete.node_id)

    # Step 2: contradictions - loop until no more are found
    max_iterations = 10  # Safety limit
    for _iteration in range(max_iterations):
        contradictions = find_contradictions(graph)
        if not contradictions:
            break
        resolved_keys: set[str] = set()
        resolved_any = False
        for a, b in contradictions:
            key = _fact_key(a)
            if key in resolved_keys:
                continue
            node_a = graph.get_node(a.node_id)
            node_b = graph.get_node(b.node_id)
            if node_a is None or node_b is None:
                continue
            if not node_a.is_active or not node_b.is_active:
                continue
            newer, older = sorted(
                (node_a, node_b), key=lambda node: (node.created_at_s, node.node_id), reverse=True
            )
            newer_trusted = node_a.metadata.get("trust") in {"high", "verified"}
            older_trusted = node_b.metadata.get("trust") in {"high", "verified"}
            if newer.node_id == node_b.node_id:
                newer_trusted, older_trusted = older_trusted, newer_trusted
            winner = resolve_contradiction(
                newer, older, newer_trusted=newer_trusted, older_trusted=older_trusted
            )
            loser = node_b if winner.node_id == node_a.node_id else node_a
            # Mark loser superseded
            from dataclasses import replace

            graph._nodes[loser.node_id] = replace(loser, is_active=False)  # noqa: SLF001
            graph.add_edge(MemoryEdge.create(winner.node_id, loser.node_id, "supersedes"))
            graph.add_edge(MemoryEdge.create(winner.node_id, loser.node_id, "contradicts"))
            report.superseded.append(loser.node_id)
            report.contradictions_resolved += 1
            resolved_keys.add(key)
            resolved_any = True
        if not resolved_any:
            break

    return report


def summarize_episodes(
    graph: MemoryGraph,
    episodes: list[MemoryNode],
    *,
    template: str = "Day summary covering {count} events: {topics}",
) -> MemoryNode | None:
    """Generate a template-based summary node for a group of episodes.

    The summary cites the episodes it covers via 'derived_from' edges. Returns
    None if the episode list is empty. The summary is added to the graph.
    """
    if not episodes:
        return None
    active = [ep for ep in episodes if ep.is_active]
    if not active:
        return None
    topics = ", ".join(sorted({ep.title for ep in active})[:5])
    body = template.format(count=len(active), topics=topics)
    title = f"summary_{active[0].created_at_s}"
    summary = MemoryNode.create(
        kind="episode",
        title=title,
        body=body,
        created_at_s=max(ep.created_at_s for ep in active),
        metadata={"summary": "true", "source_count": str(len(active))},
    )
    graph.add_node(summary)
    for ep in active:
        graph.add_edge(MemoryEdge.create(summary.node_id, ep.node_id, "derived_from"))
    return summary


def consolidate_with_summaries(
    graph: MemoryGraph,
    *,
    dedup_threshold: float = 0.85,
    episode_groups: dict[str, list[MemoryNode]] | None = None,
) -> ConsolidationReport:
    """Full consolidation pass including optional episode summary generation.

    Runs dedup, contradiction resolution, then generates summaries for each
    provided episode group.
    """
    report = consolidate_graph(graph, dedup_threshold=dedup_threshold)
    if episode_groups:
        for _key, episodes in episode_groups.items():
            summary = summarize_episodes(graph, episodes)
            if summary is not None:
                report.summary_nodes.append(summary.node_id)
    return report


def validate_consolidation_report(report: ConsolidationReport) -> list[str]:
    """Validate a consolidation report for consistency.

    Checks:
    - All merged pairs have valid node references
    - All superseded nodes are non-empty strings
    - Summary nodes are non-empty strings
    - Total changes is consistent with merge/supersede/summary counts
    """
    problems: list[str] = []

    for i, pair in enumerate(report.merged_pairs):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            problems.append(f"merged_pairs[{i}] is not a 2-element pair")
        elif not all(isinstance(node_id, str) for node_id in pair):
            problems.append(f"merged_pairs[{i}] contains non-string node ids")

    for i, superseded in enumerate(report.superseded):
        if not isinstance(superseded, str) or not superseded.strip():
            problems.append(f"superseded[{i}] is not a non-empty string")

    for i, summary in enumerate(report.summary_nodes):
        if not isinstance(summary, str) or not summary.strip():
            problems.append(f"summary_nodes[{i}] is not a non-empty string")

    expected_total = len(report.merged_pairs) + len(report.superseded) + len(report.summary_nodes)
    if report.total_changes() != expected_total:
        problems.append(
            f"total_changes ({report.total_changes()}) does not match "
            f"merge+supersede+summary count ({expected_total})"
        )

    return problems


def consolidation_statistics(report: ConsolidationReport) -> dict[str, int]:
    """Generate statistics from a consolidation report.

    Returns a dict with counts of each type of change.
    """
    return {
        "merged_pairs": len(report.merged_pairs),
        "superseded": len(report.superseded),
        "summary_nodes": len(report.summary_nodes),
        "total_changes": report.total_changes(),
    }


def consolidation_report_summary(report: ConsolidationReport) -> dict[str, object]:
    """Return summary of consolidation report."""
    return {
        "merged_count": len(report.merged_pairs),
        "superseded_count": len(report.superseded),
        "contradictions_resolved": report.contradictions_resolved,
    }


def format_consolidation_report(report: ConsolidationReport, graph: MemoryGraph) -> str:
    """Format a consolidation report as human-readable text with citations.

    Returns a markdown-formatted string describing all consolidation actions
    with references to the affected memory nodes.
    """
    lines: list[str] = []
    lines.append("# Consolidation Report\n")
    lines.append(f"- **Merged pairs**: {len(report.merged_pairs)}")
    lines.append(f"- **Superseded**: {len(report.superseded)}")
    lines.append(f"- **Summary nodes created**: {len(report.summary_nodes)}")
    lines.append(f"- **Contradictions resolved**: {report.contradictions_resolved}")
    lines.append("")

    if report.merged_pairs:
        lines.append("## Merged Near-Duplicates\n")
        for i, (winner_id, loser_id) in enumerate(report.merged_pairs[:10], 1):
            winner = graph.get_node(winner_id)
            if winner:
                lines.append(f"{i}. **{winner.title}** (`{winner_id}`)")
                lines.append(f"   - Merged with: `{loser_id}`")
        if len(report.merged_pairs) > 10:
            lines.append(f"   ... and {len(report.merged_pairs) - 10} more")
        lines.append("")

    if report.superseded:
        lines.append("## Superseded Memories\n")
        for i, node_id in enumerate(report.superseded[:10], 1):
            node = graph.get_node(node_id)
            if node:
                lines.append(f"{i}. **{node.title}** (`{node_id}`)")
            else:
                lines.append(f"{i}. `{node_id}`")
        if len(report.superseded) > 10:
            lines.append(f"   ... and {len(report.superseded) - 10} more")
        lines.append("")

    if report.summary_nodes:
        lines.append("## Episode Summaries Created\n")
        for i, summary_id in enumerate(report.summary_nodes[:10], 1):
            summary = graph.get_node(summary_id)
            if summary:
                lines.append(f"{i}. **{summary.title}** (`{summary_id}`)")
        if len(report.summary_nodes) > 10:
            lines.append(f"   ... and {len(report.summary_nodes) - 10} more")
        lines.append("")

    return "\n".join(lines)


def extract_fact_key(text: str) -> str:
    """Extract a canonical key from fact text for contradiction detection."""
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "my", "i", "at", "in", "on"}
    words = text.lower().split()
    content_words = [w for w in words if w not in stop_words and len(w) > 2]
    return " ".join(sorted(content_words[:5]))
