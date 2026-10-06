"""Tests for replay byte-equality: same seed and inputs produce identical traces."""

import tempfile
from pathlib import Path

from famulix.session import SessionRecorder


def test_replay_byte_equality():
    """Two recorders with identical inputs produce byte-identical JSONL."""
    r1 = SessionRecorder(session_id="test", seed=42)
    r1.record("query", {"text": "hello"}, timestamp_s=100)
    r1.record("response", {"text": "world"}, timestamp_s=200)

    r2 = SessionRecorder(session_id="test", seed=42)
    r2.record("query", {"text": "hello"}, timestamp_s=100)
    r2.record("response", {"text": "world"}, timestamp_s=200)

    assert r1.to_jsonl() == r2.to_jsonl()
    assert r1.digest() == r2.digest()


def test_save_and_load_byte_equality():
    """Save/load round-trip produces byte-identical output."""
    r1 = SessionRecorder(session_id="roundtrip", seed=99)
    r1.record("event", {"data": "test"}, timestamp_s=500)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "session.jsonl"
        r1.save(str(path))
        r2 = SessionRecorder.load(str(path))

    assert r1.to_jsonl() == r2.to_jsonl()
    assert r1.digest() == r2.digest()


def test_different_seeds_differ():
    """Different seeds produce different digests."""
    r1 = SessionRecorder(session_id="test", seed=1)
    r1.record("event", {}, timestamp_s=100)
    r2 = SessionRecorder(session_id="test", seed=2)
    r2.record("event", {}, timestamp_s=100)
    assert r1.digest() != r2.digest()
