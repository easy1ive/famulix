"""Tests for session checkpoint resume at arbitrary offsets."""

import pytest

from famulix.session import SessionRecorder


@pytest.fixture
def recorded_session():
    rec = SessionRecorder(session_id="ckpt-test", seed=42)
    for i in range(10):
        rec.record(f"event_{i}", {"index": i}, timestamp_s=1000 + i)
    return rec


def test_resume_from_zero_equals_full(recorded_session):
    resumed = recorded_session.resume_from_offset(0)
    assert resumed.entry_count() == recorded_session.entry_count()


def test_resume_from_end_is_empty(recorded_session):
    resumed = recorded_session.resume_from_offset(10)
    assert resumed.entry_count() == 0


def test_resume_from_middle(recorded_session):
    resumed = recorded_session.resume_from_offset(5)
    assert resumed.entry_count() == 5
    assert resumed.entries[0]["kind"] == "event_5"


def test_resume_preserves_determinism(recorded_session):
    """Resumed session digest is deterministic across calls."""
    r1 = recorded_session.resume_from_offset(3)
    r2 = recorded_session.resume_from_offset(3)
    assert r1.digest() == r2.digest()
    assert r1.digest() != recorded_session.digest()


def test_resume_invalid_offset_raises(recorded_session):
    with pytest.raises(ValueError):
        recorded_session.resume_from_offset(-1)
    with pytest.raises(ValueError):
        recorded_session.resume_from_offset(11)


def test_resume_byte_equality_across_calls(recorded_session):
    """Same offset produces byte-identical JSONL."""
    r1 = recorded_session.resume_from_offset(4)
    r2 = recorded_session.resume_from_offset(4)
    assert r1.to_jsonl() == r2.to_jsonl()
