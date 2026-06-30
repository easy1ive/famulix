"""Test replay produces identical bytes on double run."""

from famulix.session import SessionRecorder


def test_replay_determinism_double_run():
    """Verify two runs with same seed produce identical traces."""
    rec1 = SessionRecorder(session_id="s1", seed=42)
    rec1.record("event", {"type": "note", "text": "Hello"}, timestamp_s=1000)
    rec1.record("decision", {"action": "consolidate", "reason": "dedup"}, timestamp_s=1001)
    trace1 = rec1.to_jsonl()

    rec2 = SessionRecorder(session_id="s1", seed=42)
    rec2.record("event", {"type": "note", "text": "Hello"}, timestamp_s=1000)
    rec2.record("decision", {"action": "consolidate", "reason": "dedup"}, timestamp_s=1001)
    trace2 = rec2.to_jsonl()

    assert trace1 == trace2
    assert rec1.digest() == rec2.digest()
