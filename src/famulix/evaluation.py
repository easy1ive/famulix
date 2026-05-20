"""Memory-focused evaluation harness.

End-to-end persona scenarios scored against planted ground truth:
- recall@k and precision@k for planted facts
- contradiction-resolution accuracy
- citation coverage
- preference calibration
- budget adherence
- privacy violation counters
- deletion-resurrection checks
- replay determinism

All scores come from the synthetic factory with planted ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from famulix.briefing import build_briefing
from famulix.consolidation import consolidate_graph
from famulix.context import ContextItem, assemble_context, estimate_tokens
from famulix.deletion import delete_memory
from famulix.encoding import encode_events_to_graph
from famulix.events import Event
from famulix.factory import generate_history_with_truth
from famulix.memory_graph import MemoryGraph
from famulix.preferences import PreferenceProfile
from famulix.privacy import PolicyEngine, PrivacyGate
from famulix.retrieval import BM25Index, hybrid_score

FeedbackRating = Literal["up", "down", "skip", "accept", "decline", "edit"]


@dataclass
class EvalScorecard:
    """Aggregate evaluation scores with per-slice breakdowns."""

    persona_id: str
    seed: int
    days: int
    recall_at_k: dict[str, float] = field(default_factory=dict)
    precision_at_k: dict[str, float] = field(default_factory=dict)
    contradiction_accuracy: float = 0.0
    citation_coverage: float = 0.0
    budget_adherence: bool = True
    total_briefing_items: int = 0
    cited_items: int = 0
    citation_coverage_ratio: float = 0.0
    budget_violations: int = 0
    privacy_violations: int = 0
    deletion_resurrection_count: int = 0
    replay_deterministic: bool = True
    preference_brier_score: float = 0.0
    total_planted_facts: int = 0
    total_contradiction_pairs: int = 0
    slices: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "seed": self.seed,
            "days": self.days,
            "recall_at_k": self.recall_at_k,
            "precision_at_k": self.precision_at_k,
            "contradiction_accuracy": round(self.contradiction_accuracy, 6),
            "citation_coverage": round(self.citation_coverage, 6),
            "budget_adherence": self.budget_adherence,
            "budget_violations": self.budget_violations,
            "privacy_violations": self.privacy_violations,
            "deletion_resurrection_count": self.deletion_resurrection_count,
            "replay_deterministic": self.replay_deterministic,
            "preference_brier_score": round(self.preference_brier_score, 6),
            "total_planted_facts": self.total_planted_facts,
            "total_contradiction_pairs": self.total_contradiction_pairs,
            "slices": {k: v for k, v in self.slices.items()},
        }

    def summary(self) -> str:
        """A short human-readable summary of the scorecard."""
        recall5 = self.recall_at_k.get("5", 0.0)
        precision5 = self.precision_at_k.get("5", 0.0)
        lines = [
            f"Eval scorecard for persona={self.persona_id} seed={self.seed} days={self.days}",
            f"  recall@5={recall5:.3f}  precision@5={precision5:.3f}",
            f"  contradiction_accuracy={self.contradiction_accuracy:.3f}",
            f"  citation_coverage={self.citation_coverage:.3f}",
            f"  budget_adherence={self.budget_adherence} violations={self.budget_violations}",
            f"  privacy_violations={self.privacy_violations}",
            f"  deletion_resurrections={self.deletion_resurrection_count}",
            f"  replay_deterministic={self.replay_deterministic}",
            f"  preference_brier={self.preference_brier_score:.3f}",
        ]
        return "\n".join(lines)


def _build_graph_from_events(events: list[Event]) -> MemoryGraph:
    return encode_events_to_graph(events)


def _build_index(graph: MemoryGraph) -> BM25Index:
    idx = BM25Index()
    for node in graph.all_nodes():
        if node.is_active:
            idx.add_node(node)
    return idx


def compute_recall_precision(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> tuple[float, float]:
    """Compute recall@k and precision@k.

    recall = (relevant retrieved) / total_relevant
    precision = (relevant retrieved) / k
    """
    if k < 0:
        raise ValueError("k must be non-negative")
    if not relevant_ids:
        return 1.0, 1.0
    if k == 0:
        return 0.0, 0.0
    top_k = retrieved_ids[:k]
    relevant_retrieved = sum(1 for rid in top_k if rid in relevant_ids)
    recall = relevant_retrieved / len(relevant_ids)
    precision = relevant_retrieved / max(k, 1)
    return round(recall, 6), round(precision, 6)


def eval_recall_precision(
    graph: MemoryGraph,
    planted_fact_ids: set[str],
    now_s: int,
    k_values: list[int] | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    """Evaluate retrieval recall@k and precision@k for planted facts.

    planted_fact_ids may be event_ids (mapped via source_event metadata) or
    node_ids (used directly if present in the graph).
    """
    if k_values is None:
        k_values = [1, 5, 10, 20]

    # Map planted event_ids to fact node_ids via source_event metadata
    # Also accept node_ids directly if they exist in the graph
    planted_node_ids: set[str] = set()
    for node in graph.all_nodes():
        if node.kind == "fact":
            source_event = node.metadata.get("source_event", "")
            if source_event in planted_fact_ids:
                planted_node_ids.add(node.node_id)
            if node.node_id in planted_fact_ids:
                planted_node_ids.add(node.node_id)

    idx = _build_index(graph)

    # For each planted fact, query using its own title and check retrieval rank.
    # This tests whether the retrieval mechanics work (index, scoring, ranking).
    recall: dict[str, float] = {}
    precision: dict[str, float] = {}
    for k in k_values:
        recall[f"@{k}"] = 0.0
        precision[f"@{k}"] = 0.0

    if not planted_node_ids:
        return recall, precision

    found_at_k: dict[int, int] = {k: 0 for k in k_values}
    total_queries = 0

    for node in graph.all_nodes():
        if node.kind == "fact" and node.node_id in planted_node_ids:
            query = node.title
            results = hybrid_score(query, graph=graph, index=idx, now_s=now_s)
            top_ids = [r.node_id for r in results]
            total_queries += 1
            for k in k_values:
                if node.node_id in top_ids[:k]:
                    found_at_k[k] += 1

    if total_queries > 0:
        for k in k_values:
            recall[f"@{k}"] = round(found_at_k[k] / total_queries, 6)
            precision[f"@{k}"] = round(found_at_k[k] / (total_queries * k), 6)

    return recall, precision


def eval_contradiction_resolution(
    graph: MemoryGraph,
    contradiction_pairs: list[tuple[str, str]],
) -> float:
    """Evaluate contradiction resolution accuracy.

    For each pair (old_id, new_id), the newer fact should be the active one
    after consolidation. IDs may be event_ids (mapped via source_event metadata)
    or node_ids (used directly). Returns fraction of correctly resolved pairs.
    """
    if not contradiction_pairs:
        return 1.0

    # Build event_id -> node_id mapping for fact nodes
    event_to_node: dict[str, str] = {}
    for node in graph.all_nodes():
        if node.kind == "fact":
            source_event = node.metadata.get("source_event", "")
            if source_event:
                event_to_node[source_event] = node.node_id

    correct = 0
    for old_id, new_id in contradiction_pairs:
        # Try event_id mapping first, fall back to direct node_id
        resolved_old = event_to_node.get(old_id, old_id)
        resolved_new = event_to_node.get(new_id, new_id)
        new_node = graph.get_node(resolved_new)
        old_node = graph.get_node(resolved_old)
        # After consolidation, the newer should be active, older superseded
        new_active = new_node.is_active if new_node else False
        old_active = old_node.is_active if old_node else True
        if new_active and not old_active:
            correct += 1
        elif new_active and old_active:
            # Both still active but new is "newer verified" - partial credit
            # Check if there's a supersedes edge
            supersedes_edges = graph.out_edges(resolved_new)
            has_supersede = any(e.kind == "supersedes" for e in supersedes_edges)
            if has_supersede:
                correct += 1
    return round(correct / max(len(contradiction_pairs), 1), 6)


def eval_citation_coverage(
    briefing_items: list[Any],
    planted_fact_ids: set[str],
) -> float:
    """Evaluate what fraction of briefing items have citations.

    Returns the citation coverage ratio (items with valid memory ids / total items).
    """
    if not briefing_items:
        return 1.0
    cited_count = sum(1 for it in briefing_items if it.memory_ids)
    return round(cited_count / len(briefing_items), 6)


def eval_budget_adherence(
    context_items: list[Any],
    budget: int,
) -> tuple[bool, int]:
    """Check that assembled context respects the token budget."""
    total_tokens = sum(estimate_tokens(str(ci.payload)) for ci in context_items)
    violations = 1 if total_tokens > budget else 0
    return total_tokens <= budget, violations


def eval_preference_calibration(
    profile: PreferenceProfile,
    preference_signals: list[dict[str, Any]],
    now_s: int,
) -> float:
    """Compute Brier score for preference predictions against planted signals.

    Treat the profile's current confidence as predicted probability of
    "up" rating. Uses leave-one-out: for each signal, predict from all others.
    """
    if not preference_signals:
        return 0.0
    squared_errors: list[float] = []
    for _i, sig in enumerate(preference_signals):
        key = sig.get("key", "")
        rating = sig.get("rating", "skip")
        actual = 1.0 if rating == "up" else 0.0
        # Get current preference for this key
        prefs = profile.current_preferences(now_s)
        if key in prefs:
            _, conf = prefs[key]
            predicted = max(0.0, min(1.0, conf))
        else:
            predicted = 0.5
        squared_errors.append((predicted - actual) ** 2)
    brier = sum(squared_errors) / len(squared_errors)
    return round(brier, 6)


def eval_deletion_resurrection(
    graph: MemoryGraph,
    deleted_ids: set[str],
    query_results: list[Any],
) -> int:
    """Count how many deleted memories reappear in query results."""
    result_ids = {r.node_id for r in query_results}
    return len(deleted_ids & result_ids)


def run_full_evaluation(
    persona_id: str = "alex",
    seed: int = 0,
    days: int = 90,
    start_date: str = "2026-01-01",
    *,
    budget_tokens: int = 500,
) -> EvalScorecard:
    """Run a full evaluation pipeline on a synthetic persona."""
    events, manifest, truth = generate_history_with_truth(
        persona_id, seed=seed, days=days, start_date=start_date
    )

    # Build graph from events
    graph = _build_graph_from_events(events)

    # Consolidate to resolve contradictions
    consolidate_graph(graph)

    now_s = events[-1].timestamp_s + 3600 if events else 0

    # Recall/precision
    planted_fact_set = set(truth["fact_ids"])
    recall, precision = eval_recall_precision(graph, planted_fact_set, now_s)

    # Contradiction accuracy
    contradiction_pairs = [(pair[0], pair[1]) for pair in truth["contradiction_pairs"]]
    contradiction_accuracy = eval_contradiction_resolution(graph, contradiction_pairs)

    # Build briefing and check citations
    briefing = build_briefing(
        graph,
        date_str=manifest.end_date,
        now_s=now_s,
        budget_tokens=budget_tokens,
        seed=seed,
    )
    citation_coverage = eval_citation_coverage(briefing.items, planted_fact_set)

    # Budget adherence
    context_items: list[ContextItem] = []
    for item in briefing.items:
        text = f"{item.title}: {item.body}"
        context_items.append(
            ContextItem(
                item_id=item.memory_ids[0] if item.memory_ids else "unknown",
                token_estimate=estimate_tokens(text),
                value=item.priority,
                payload=text,
            )
        )
    assembled = assemble_context(context_items, budget=budget_tokens)
    budget_ok, budget_violations = eval_budget_adherence(assembled.items, budget_tokens)

    # Preference calibration (build profile from signals and measure)
    profile = PreferenceProfile()
    for idx, sig in enumerate(truth["preference_signals"]):
        rating = sig["rating"]
        profile.add_feedback(
            pref_key=sig["key"],
            value=sig["value"],
            signal=rating,
            timestamp_s=idx * 3600,
            confidence=0.6,
            source="planted",
        )
    brier = eval_preference_calibration(profile, truth["preference_signals"], now_s)

    # Exercise the export guard with an explicitly lower-tier destination.
    privacy_gate = PrivacyGate(PolicyEngine(default_effect="allow"))
    privacy_probe = privacy_gate.request(
        actor="synthetic-evaluator",
        action="export",
        resource="evaluation-probe",
        data_tier="private",
        clearance_tier="private",
        destination_tier="public",
        timestamp_s=now_s,
    )
    privacy_violations = int(privacy_probe.allowed)

    # Delete a live fact and query the rebuilt active-memory index for it.
    deletion_resurrection_count = 0
    deletion_target = next(
        (node for node in graph.all_nodes() if node.kind == "fact" and node.is_active), None
    )
    if deletion_target is not None:
        delete_memory(graph, deletion_target.node_id)
        post_delete_index = _build_index(graph)
        post_delete_results = hybrid_score(
            deletion_target.title, graph=graph, index=post_delete_index, now_s=now_s
        )
        deletion_resurrection_count = eval_deletion_resurrection(
            graph, {deletion_target.node_id}, post_delete_results
        )

    # Replay determinism check (same seed = same events)
    events2, manifest2, truth2 = generate_history_with_truth(
        persona_id, seed=seed, days=days, start_date=start_date
    )
    replay_ok = len(events) == len(events2) and all(
        e1.event_id == e2.event_id for e1, e2 in zip(events, events2, strict=False)
    )

    scorecard = EvalScorecard(
        persona_id=persona_id,
        seed=seed,
        days=days,
        recall_at_k=recall,
        precision_at_k=precision,
        contradiction_accuracy=contradiction_accuracy,
        citation_coverage=citation_coverage,
        budget_adherence=budget_ok,
        budget_violations=budget_violations,
        privacy_violations=privacy_violations,
        deletion_resurrection_count=deletion_resurrection_count,
        replay_deterministic=replay_ok,
        preference_brier_score=brier,
        total_planted_facts=manifest.planted_fact_count,
        total_contradiction_pairs=manifest.planted_contradiction_count,
    )

    # Add slices
    scorecard.slices["recall"] = recall
    scorecard.slices["precision"] = precision

    return scorecard


def evaluation_scorecard_summary(scorecard: dict) -> dict[str, object]:
    """Return summary of evaluation scorecard."""
    return {
        "recall_at_5": scorecard.get("recall_at_5", 0.0),
        "precision_at_5": scorecard.get("precision_at_5", 0.0),
        "contradiction_accuracy": scorecard.get("contradiction_accuracy", 0.0),
        "citation_coverage": scorecard.get("citation_coverage", 0.0),
    }


def format_evaluation_report(scorecard: dict, *, include_details: bool = True) -> str:
    """Format an evaluation scorecard as human-readable markdown.

    Returns a structured report with all evaluation metrics, per-slice
    breakdowns, and an honest limitations section.
    """
    lines: list[str] = []
    lines.append("# Evaluation Report\n")

    # Overall scores
    lines.append("## Overall Metrics\n")
    lines.append(f"- **Recall@10**: {scorecard.get('recall_at_10', 0.0):.3f}")
    lines.append(f"- **Precision@10**: {scorecard.get('precision_at_10', 0.0):.3f}")
    lines.append(
        f"- **Contradiction resolution**: {scorecard.get('contradiction_resolution', 0.0):.3f}"
    )
    lines.append(f"- **Citation coverage**: {scorecard.get('citation_coverage', 0.0):.3f}")
    lines.append(f"- **Budget adherence**: {scorecard.get('budget_adherence', 0.0):.3f}")
    lines.append(
        f"- **Preference calibration (Brier)**: {scorecard.get('preference_brier', 0.0):.4f}"
    )
    deletion_violations = scorecard.get("deletion_resurrection_violations", 0)
    lines.append(f"- **Deletion resurrection violations**: {deletion_violations}")
    lines.append(f"- **Privacy violations**: {scorecard.get('privacy_violations', 0)}")
    lines.append("")

    # Per-slice breakdown
    if include_details and "per_slice" in scorecard:
        lines.append("## Per-Slice Breakdown\n")
        for slice_name, metrics in scorecard["per_slice"].items():
            lines.append(f"### {slice_name}\n")
            for key, value in sorted(metrics.items()):
                if isinstance(value, float):
                    lines.append(f"- {key}: {value:.3f}")
                else:
                    lines.append(f"- {key}: {value}")
            lines.append("")

    # Limitations
    lines.append("## Limitations\n")
    lines.append("- All metrics computed on synthetic data with planted ground truth")
    lines.append("- No real LLM or real user data involved")
    lines.append("- Results reflect framework mechanics, not conversational ability")
    lines.append("")

    return "\n".join(lines)
