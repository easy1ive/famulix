"""Tests for session diff output format and content."""

from famulix.session import SessionRecorder, session_diff


def test_diff_identical_sessions():
    a = SessionRecorder(session_id="s1", seed=42)
    a.record("event", {"x": 1}, timestamp_s=100)
    b = SessionRecorder(session_id="s1", seed=42)
    b.record("event", {"x": 1}, timestamp_s=100)

    diff = session_diff(a, b)
    assert diff["identical"] is True
    assert diff["length_diff"] == 0


def test_diff_different_sessions():
    a = SessionRecorder(session_id="s1", seed=42)
    a.record("event_a", {"x": 1}, timestamp_s=100)
    b = SessionRecorder(session_id="s2", seed=42)
    b.record("event_b", {"y": 2}, timestamp_s=200)

    diff = session_diff(a, b)
    assert diff["identical"] is False


def test_diff_different_lengths():
    a = SessionRecorder(session_id="s1", seed=42)
    a.record("e1", {"x": 1}, timestamp_s=100)
    a.record("e2", {"x": 2}, timestamp_s=200)

    b = SessionRecorder(session_id="s2", seed=42)
    b.record("e1", {"x": 1}, timestamp_s=100)

    diff = session_diff(a, b)
    assert diff["length_diff"] == 1
    assert diff["a_length"] == 2
    assert diff["b_length"] == 1


def test_diff_digests_differ():
    a = SessionRecorder(session_id="s1", seed=1)
    a.record("event", {"data": "alpha"}, timestamp_s=100)
    b = SessionRecorder(session_id="s2", seed=2)
    b.record("event", {"data": "beta"}, timestamp_s=100)

    diff = session_diff(a, b)
    assert diff["a_digest"] != diff["b_digest"]


def test_diff_first_difference_index():
    a = SessionRecorder(session_id="s1", seed=42)
    a.record("same", {}, timestamp_s=100)
    a.record("different_a", {}, timestamp_s=200)

    b = SessionRecorder(session_id="s1", seed=42)
    b.record("same", {}, timestamp_s=100)
    b.record("different_b", {}, timestamp_s=200)

    diff = session_diff(a, b)
    assert diff["first_difference"] == 1
