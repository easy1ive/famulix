"""Double-run determinism across the full offline pipeline.

Every digest here comes from seeded synthetic histories with planted content.
The suite pins byte-level reproducibility of the mechanics; it makes no claim
about real assistant or model quality.
"""

from __future__ import annotations

import hashlib

from famulix.briefing import build_briefing, render_briefing_html
from famulix.consolidation import consolidate_graph
from famulix.encoding import encode_events_to_graph
from famulix.envelope import Envelope
from famulix.evaluation import run_full_evaluation
from famulix.events import Event
from famulix.factory import generate_history_with_truth
from famulix.memory_graph import MemoryGraph
from famulix.utils import stable_json_dumps


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_pipeline(seed: int, days: int = 7) -> dict[str, str]:
    """Run factory -> encode -> consolidate -> brief -> evaluate and digest each stage."""
    events, manifest, _truth = generate_history_with_truth(
        "alex", seed=seed, days=days, start_date="2026-04-01"
    )
    events_jsonl = "\n".join(event.to_envelope().to_jsonl_line() for event in events)
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)
    now_s = events[-1].timestamp_s + 3600
    briefing = build_briefing(
        graph,
        date_str=manifest.end_date,
        now_s=now_s,
        budget_tokens=320,
        seed=seed,
        config_hash=manifest.checksum,
    )
    html = render_briefing_html(briefing, graph=graph)
    scorecard = run_full_evaluation("alex", seed=seed, days=days, start_date="2026-04-01")
    return {
        "events": _digest(events_jsonl),
        "graph": _digest(stable_json_dumps(graph.to_dict())),
        "briefing_html": _digest(html),
        "scorecard": _digest(stable_json_dumps(scorecard.to_dict())),
    }


def test_pipeline_double_run_is_byte_identical() -> None:
    for seed in (0, 1, 2):
        first = run_pipeline(seed)
        second = run_pipeline(seed)
        assert first == second, f"pipeline digests diverged for seed {seed}"


def test_different_seeds_produce_different_digests() -> None:
    assert run_pipeline(0) != run_pipeline(1)


def test_event_jsonl_roundtrip_is_lossless() -> None:
    events, _manifest, _truth = generate_history_with_truth(
        "alex", seed=5, days=7, start_date="2026-04-01"
    )
    lines = [event.to_envelope().to_jsonl_line() for event in events]
    restored = [Event.from_envelope(Envelope.from_jsonl_line(line)) for line in lines]
    assert [event.to_envelope().to_jsonl_line() for event in restored] == lines


def test_graph_serialization_roundtrip_is_lossless() -> None:
    events, _manifest, _truth = generate_history_with_truth(
        "alex", seed=5, days=7, start_date="2026-04-01"
    )
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)
    payload = stable_json_dumps(graph.to_dict())
    restored = MemoryGraph.from_dict(graph.to_dict())
    assert stable_json_dumps(restored.to_dict()) == payload
