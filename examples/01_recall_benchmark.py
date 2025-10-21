"""90-day persona recall benchmark.

Generates a 90-day synthetic personal history, encodes it into a memory
graph, consolidates contradictions, and measures recall@k / precision@k
for planted facts. All data is synthetic and deterministic for a given seed.

Run: python examples/01_recall_benchmark.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from the repo root without installation
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from famulix.consolidation import consolidate_graph
from famulix.encoding import encode_events_to_graph
from famulix.evaluation import eval_recall_precision
from famulix.factory import generate_history_with_truth


def main() -> int:
    persona_id = "alex"
    seed = 42
    days = 90

    print("=== 90-Day Persona Recall Benchmark ===")
    print(f"Persona: {persona_id}")
    print(f"Seed: {seed}")
    print(f"Days: {days}")
    print()

    # Generate synthetic history with ground truth
    print("Generating synthetic history...")
    events, manifest, truth = generate_history_with_truth(
        persona_id=persona_id, seed=seed, days=days
    )
    print(f"  Total events: {manifest.event_count}")
    print(f"  By type: {json.dumps(manifest.by_type)}")
    print(f"  Planted facts: {manifest.planted_fact_count}")
    print(f"  Planted contradictions: {manifest.planted_contradiction_count}")
    print(f"  Planted preference signals: {manifest.planted_preference_count}")
    print(f"  Checksum: {manifest.checksum}")
    print()

    # Encode into memory graph
    print("Encoding events into memory graph...")
    graph = encode_events_to_graph(events)
    node_counts: dict[str, int] = {}
    for node in graph.all_nodes():
        node_counts[node.kind] = node_counts.get(node.kind, 0) + 1
    print(f"  Total nodes: {graph.node_count()}")
    print(f"  By kind: {json.dumps(node_counts)}")
    print(f"  Total edges: {graph.edge_count()}")
    print()

    # Consolidate
    print("Consolidating (dedup + contradiction resolution)...")
    report = consolidate_graph(graph)
    print(f"  Merged duplicates: {len(report.merged_pairs)}")
    print(f"  Superseded facts: {len(report.superseded)}")
    print(f"  Contradictions resolved: {report.contradictions_resolved}")
    print()

    # Evaluate recall/precision
    print("Evaluating retrieval recall@k / precision@k...")
    now_s = events[-1].timestamp_s + 3600
    planted_ids = set(truth["fact_ids"])
    recall, precision = eval_recall_precision(
        graph, planted_ids, now_s, k_values=[1, 5, 10, 20, 50]
    )
    print()
    print(f"{'k':>4}  {'Recall':>8}  {'Precision':>10}")
    print("-" * 30)
    for k in sorted(recall.keys(), key=lambda x: int(x.lstrip("@"))):
        print(f"{k:>4}  {recall[k]:8.4f}  {precision[k]:10.4f}")
    print()

    # Determinism check
    print("Verifying determinism (second run should match)...")
    events2, manifest2, truth2 = generate_history_with_truth(
        persona_id=persona_id, seed=seed, days=days
    )
    same_events = len(events) == len(events2) and all(
        e1.event_id == e2.event_id for e1, e2 in zip(events, events2, strict=False)
    )
    print(f"  Event ids match: {same_events}")
    print(f"  Checksums match: {manifest.checksum == manifest2.checksum}")
    print()

    print("=== Done ===")
    print()
    print("Interpretation:")
    print("  - Recall@k measures what fraction of planted facts appear in top-k results.")
    print("  - Precision@k measures what fraction of top-k results are planted facts.")
    print("  - Higher k generally yields higher recall but lower precision.")
    print("  - These scores describe retrieval mechanics on synthetic data only.")
    print()
    print("Note: All scores come from synthetic data with planted ground truth.")
    print("      No real LLM, no real user data, no network calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
