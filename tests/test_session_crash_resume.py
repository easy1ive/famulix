"""Test session checkpoint and resume under simulated crash."""

from famulix.session import SessionRecorder


def test_session_resume_after_crash():
    """Verify session can resume from checkpoint after simulated crash."""
    rec1 = SessionRecorder(session_id="test", seed=42)
    rec1.record("event1", {"data": "first"}, timestamp_s=100)
    rec1.record("event2", {"data": "second"}, timestamp_s=200)

    checkpoint = rec1.checkpoint()

    # Simulate crash: create new recorder from checkpoint
    rec2 = SessionRecorder.resume_from(checkpoint, rec1)
    rec2.record("event3", {"data": "third"}, timestamp_s=300)

    assert rec2.entry_count() == 3
    assert rec2.verify()
    assert rec2.entries[2]["kind"] == "event3"


def test_session_checkpoint_determinism():
    """Two runs with same seed produce identical checkpoints."""
    rec1 = SessionRecorder(session_id="det", seed=123)
    rec1.record("a", {"x": 1}, timestamp_s=10)
    rec1.record("b", {"x": 2}, timestamp_s=20)

    rec2 = SessionRecorder(session_id="det", seed=123)
    rec2.record("a", {"x": 1}, timestamp_s=10)
    rec2.record("b", {"x": 2}, timestamp_s=20)

    assert rec1.checkpoint() == rec2.checkpoint()
    assert rec1.digest() == rec2.digest()
