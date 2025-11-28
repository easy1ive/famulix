"""Tests for session record and replay."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from famulix.session import SessionRecorder, session_diff


def test_record_adds_entries() -> None:
    rec = SessionRecorder(session_id="s1", seed=42)
    h = rec.record("event", {"text": "hello"}, 100)
    assert len(rec.entries) == 1
    assert h
    assert rec.entries[0]["kind"] == "event"
    assert rec.entries[0]["_hash"] == h


def test_record_snapshots_payload_and_rejects_non_json_values() -> None:
    rec = SessionRecorder(session_id="s1", seed=4)
    payload = {"nested": {"choice": "brief"}}
    rec.record("decision", payload, 10)
    payload["nested"]["choice"] = "changed"

    assert rec.entries[0]["payload"]["nested"]["choice"] == "brief"
    assert rec.verify()
    with pytest.raises(ValueError, match="finite JSON"):
        rec.record("decision", {"score": float("nan")}, 11)


@pytest.mark.parametrize("timestamp", [-1, 1.5, True])
def test_record_rejects_invalid_timestamp(timestamp: int) -> None:
    with pytest.raises(ValueError, match="timestamp"):
        SessionRecorder(session_id="s1").record("event", {}, timestamp)


def test_verify_passes_for_valid_chain() -> None:
    rec = SessionRecorder(session_id="s1", seed=42)
    rec.record("event", {"a": 1}, 100)
    rec.record("decision", {"action": "go"}, 200)
    rec.record("recall", {"n_results": 5}, 300)
    assert rec.verify() is True


def test_verify_fails_for_tampered() -> None:
    rec = SessionRecorder(session_id="s1", seed=42)
    rec.record("event", {"a": 1}, 100)
    rec.record("decision", {"action": "go"}, 200)
    # Tamper with the first entry
    rec.entries[0]["payload"]["a"] = 999
    assert rec.verify() is False


def test_save_and_load_roundtrip() -> None:
    rec = SessionRecorder(session_id="s1", seed=42)
    rec.record("event", {"text": "hello"}, 100)
    rec.record("recall", {"q": "test"}, 200)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "session.jsonl"
        rec.save(path)
        loaded = SessionRecorder.load(path)
        assert loaded.session_id == rec.session_id
        assert loaded.seed == rec.seed
        assert len(loaded.entries) == len(rec.entries)
        assert loaded.verify() is True
        assert loaded.digest() == rec.digest()


def test_digest_deterministic() -> None:
    a = SessionRecorder(session_id="s1", seed=42)
    a.record("event", {"x": 1}, 100)
    a.record("event", {"x": 2}, 200)
    b = SessionRecorder(session_id="s1", seed=42)
    b.record("event", {"x": 1}, 100)
    b.record("event", {"x": 2}, 200)
    assert a.digest() == b.digest()


def test_jsonl_bytes_ignore_mapping_insertion_order() -> None:
    first = SessionRecorder(session_id="stable", seed=8)
    second = SessionRecorder(session_id="stable", seed=8)
    first.record("decision", {"alpha": 1, "nested": {"left": 2, "right": 3}}, 100)
    second.record("decision", {"nested": {"right": 3, "left": 2}, "alpha": 1}, 100)

    assert first.to_jsonl().encode("utf-8") == second.to_jsonl().encode("utf-8")
    assert first.verify() and second.verify()


def test_load_rejects_tampered_frame(tmp_path: Path) -> None:
    recorder = SessionRecorder(session_id="stable", seed=8)
    recorder.record("decision", {"choice": "brief"}, 100)
    path = tmp_path / "session.jsonl"
    path.write_text(recorder.to_jsonl().replace('"choice": "brief"', '"choice": "other"'))

    with pytest.raises(ValueError, match="checksum"):
        SessionRecorder.load(path)


@pytest.mark.parametrize("content", ["{broken}\n", "[]\n", "\n"])
def test_load_rejects_malformed_frames(tmp_path: Path, content: str) -> None:
    path = tmp_path / "session.jsonl"
    path.write_text(content)

    with pytest.raises(ValueError):
        SessionRecorder.load(path)


def test_digest_different_for_different_content() -> None:
    a = SessionRecorder(session_id="s1", seed=42)
    a.record("event", {"x": 1}, 100)
    b = SessionRecorder(session_id="s1", seed=42)
    b.record("event", {"x": 999}, 100)
    assert a.digest() != b.digest()


def test_verify_returns_false_for_in_memory_sequence_or_identity_drift() -> None:
    rec = SessionRecorder(session_id="s1", seed=42)
    rec.record("event", {"x": 1}, 100)
    rec.entries[0]["seq"] = 3
    assert not rec.verify()

    rec.entries[0]["seq"] = 0
    rec.entries[0]["session_id"] = "other"
    assert not rec.verify()


def test_verify_fails_closed_for_non_json_payload_mutation() -> None:
    rec = SessionRecorder(session_id="s1", seed=42)
    rec.record("event", {"x": 1}, 100)
    rec.entries[0]["payload"] = {"unsupported": {1, 2}}

    assert not rec.verify()


def test_session_diff_identical() -> None:
    a = SessionRecorder(session_id="s1", seed=42)
    a.record("event", {"x": 1}, 100)
    b = SessionRecorder(session_id="s1", seed=42)
    b.record("event", {"x": 1}, 100)
    diff = session_diff(a, b)
    assert diff["identical"] is True
    assert diff["length_diff"] == 0


def test_session_diff_different() -> None:
    a = SessionRecorder(session_id="s1", seed=42)
    a.record("event", {"x": 1}, 100)
    b = SessionRecorder(session_id="s1", seed=42)
    b.record("event", {"x": 1}, 100)
    b.record("event", {"x": 2}, 200)
    diff = session_diff(a, b)
    assert diff["identical"] is False
    assert diff["length_diff"] == -1


def test_multiple_entry_order() -> None:
    rec = SessionRecorder(session_id="s1", seed=42)
    rec.record("a", {}, 100)
    rec.record("b", {}, 200)
    rec.record("c", {}, 300)
    assert [e["kind"] for e in rec.entries] == ["a", "b", "c"]
    assert [e["seq"] for e in rec.entries] == [0, 1, 2]


def test_session_checkpoint_resumes_only_matching_trace() -> None:
    import pytest

    from famulix.session import SessionRecorder

    recorder = SessionRecorder("daily", seed=4)
    recorder.record("recall", {"id": "m1"}, 10)
    checkpoint = recorder.checkpoint()
    assert SessionRecorder.resume_from(checkpoint, recorder) is recorder
    recorder.record("brief", {"id": "b1"}, 11)
    with pytest.raises(ValueError, match="stale"):
        SessionRecorder.resume_from(checkpoint, recorder)


def test_session_loader_rejects_extra_frame_fields(tmp_path) -> None:
    import json

    import pytest

    from famulix.session import SessionRecorder

    path = tmp_path / "session.jsonl"
    path.write_text(
        json.dumps(
            {
                "session_id": "x",
                "seq": 0,
                "kind": "k",
                "timestamp_s": 0,
                "payload": {},
                "seed": 0,
                "_hash": "x",
                "extra": 1,
            }
        )
        + "\n"
    )
    with pytest.raises(ValueError, match="unknown or missing"):
        SessionRecorder.load(path)


def test_session_diff_reports_first_changed_frame() -> None:
    from famulix.session import SessionRecorder, session_diff

    left = SessionRecorder("x")
    right = SessionRecorder("x")
    left.record("a", {"value": 1}, 0)
    right.record("a", {"value": 2}, 0)
    result = session_diff(left, right)
    assert result["identical"] is False
    assert result["first_difference"] == 0


def test_entry_count_matches_records() -> None:
    rec = SessionRecorder("s1")
    assert rec.entry_count() == 0
    rec.record("event", {"data": 1}, 100)
    assert rec.entry_count() == 1
    rec.record("decision", {"choice": "a"}, 200)
    assert rec.entry_count() == 2


def test_kinds_seen_counts_each_kind() -> None:
    rec = SessionRecorder("s2")
    rec.record("event", {"data": 1}, 100)
    rec.record("event", {"data": 2}, 200)
    rec.record("recall", {"query": "x"}, 300)
    rec.record("event", {"data": 3}, 400)
    rec.record("decision", {"choice": "y"}, 500)
    counts = rec.kinds_seen()
    assert counts["event"] == 3
    assert counts["recall"] == 1
    assert counts["decision"] == 1
    assert sum(counts.values()) == rec.entry_count()


def test_session_diff_reports_field_level_differences() -> None:
    from famulix.session import SessionRecorder, session_diff

    a = SessionRecorder(session_id="s1", seed=42)
    a.record("event", {"key": "value1"}, timestamp_s=100)
    a.record("event", {"key": "value2"}, timestamp_s=200)

    b = SessionRecorder(session_id="s1", seed=42)
    b.record("event", {"key": "value1"}, timestamp_s=100)
    b.record("event", {"key": "different"}, timestamp_s=200)

    diff = session_diff(a, b)
    assert not diff["identical"]
    assert diff["first_difference"] == 1
    assert len(diff["field_differences"]) >= 1
    frame_diff = diff["field_differences"][0]
    assert frame_diff["frame_index"] == 1
    assert any(fd["field"] == "payload" for fd in frame_diff["fields"])


def test_session_diff_identical_sessions_have_no_field_diffs() -> None:
    from famulix.session import SessionRecorder, session_diff

    a = SessionRecorder(session_id="s1", seed=42)
    a.record("event", {"data": "same"}, timestamp_s=100)

    b = SessionRecorder(session_id="s1", seed=42)
    b.record("event", {"data": "same"}, timestamp_s=100)

    diff = session_diff(a, b)
    assert diff["identical"]
    assert diff["field_differences"] == []


def test_session_diff_handles_length_mismatch() -> None:
    from famulix.session import SessionRecorder, session_diff

    a = SessionRecorder(session_id="s1", seed=42)
    a.record("event", {"data": "one"}, timestamp_s=100)

    b = SessionRecorder(session_id="s1", seed=42)
    b.record("event", {"data": "one"}, timestamp_s=100)
    b.record("event", {"data": "two"}, timestamp_s=200)

    diff = session_diff(a, b)
    assert not diff["identical"]
    assert diff["length_diff"] == -1
    assert diff["first_difference"] == 1


def test_session_checkpoint_captures_state() -> None:
    from famulix.session import SessionRecorder

    rec = SessionRecorder(session_id="test_session", seed=42)
    rec.record("event", {"data": "one"}, timestamp_s=100)
    rec.record("event", {"data": "two"}, timestamp_s=200)
    checkpoint = rec.checkpoint()
    assert checkpoint["session_id"] == "test_session"
    assert checkpoint["seed"] == 42
    assert checkpoint["next_seq"] == 2
    assert "digest" in checkpoint


def test_session_resume_from_checkpoint() -> None:
    from famulix.session import SessionRecorder

    rec1 = SessionRecorder(session_id="test", seed=42)
    rec1.record("event", {"data": "one"}, timestamp_s=100)
    checkpoint = rec1.checkpoint()
    rec2 = SessionRecorder.resume_from(checkpoint, rec1)
    assert rec2.session_id == rec1.session_id
    assert rec2.entry_count() == rec1.entry_count()


def test_session_checkpoint_rejects_stale_cursor() -> None:
    import pytest

    from famulix.session import SessionRecorder

    rec = SessionRecorder(session_id="test", seed=42)
    rec.record("event", {"data": "one"}, timestamp_s=100)
    checkpoint = rec.checkpoint()
    rec.record("event", {"data": "two"}, timestamp_s=200)
    with pytest.raises(ValueError, match="stale"):
        SessionRecorder.resume_from(checkpoint, rec)


def test_session_checkpoint_rejects_wrong_session() -> None:
    import pytest

    from famulix.session import SessionRecorder

    rec1 = SessionRecorder(session_id="session1", seed=42)
    rec1.record("event", {"data": "one"}, timestamp_s=100)
    checkpoint = rec1.checkpoint()
    rec2 = SessionRecorder(session_id="session2", seed=42)
    rec2.record("event", {"data": "one"}, timestamp_s=100)
    with pytest.raises(ValueError, match="does not match"):
        SessionRecorder.resume_from(checkpoint, rec2)


def test_session_verify_detects_tampering() -> None:
    from famulix.session import SessionRecorder

    rec = SessionRecorder(session_id="test", seed=42)
    rec.record("event", {"data": "one"}, timestamp_s=100)
    rec.record("event", {"data": "two"}, timestamp_s=200)
    assert rec.verify()
    rec.entries[1]["payload"] = {"data": "tampered"}
    assert not rec.verify()


def test_session_kinds_seen_counts_events() -> None:
    from famulix.session import SessionRecorder

    rec = SessionRecorder(session_id="test", seed=42)
    rec.record("event", {"data": "one"}, timestamp_s=100)
    rec.record("decision", {"result": "yes"}, timestamp_s=200)
    rec.record("event", {"data": "two"}, timestamp_s=300)
    kinds = rec.kinds_seen()
    assert kinds["event"] == 2
    assert kinds["decision"] == 1


def test_validate_session_valid() -> None:
    from famulix.session import SessionRecorder, validate_session

    rec = SessionRecorder(session_id="test", seed=42)
    rec.record("event", {"data": "one"}, timestamp_s=100)
    rec.record("event", {"data": "two"}, timestamp_s=200)

    result = validate_session(rec)
    assert result["valid"]
    assert result["entry_count"] == 2
    assert result["checksum_valid"]
    assert result["timestamp_monotonic"]
    assert result["errors"] == []


def test_validate_session_detects_tampering() -> None:
    from famulix.session import SessionRecorder, validate_session

    rec = SessionRecorder(session_id="test", seed=42)
    rec.record("event", {"data": "one"}, timestamp_s=100)
    rec.entries[0]["payload"] = {"data": "tampered"}

    result = validate_session(rec)
    assert not result["valid"]
    assert not result["checksum_valid"]
    assert len(result["errors"]) > 0


def test_validate_session_detects_non_monotonic_timestamps() -> None:
    from famulix.session import SessionRecorder, validate_session

    rec = SessionRecorder(session_id="test", seed=42)
    rec.record("event", {"data": "one"}, timestamp_s=200)
    rec.record("event", {"data": "two"}, timestamp_s=100)

    result = validate_session(rec)
    assert not result["valid"]
    assert not result["timestamp_monotonic"]
    assert any("timestamp" in e for e in result["errors"])


def test_validate_session_empty() -> None:
    from famulix.session import SessionRecorder, validate_session

    rec = SessionRecorder(session_id="test", seed=42)
    result = validate_session(rec)
    assert result["valid"]
    assert result["entry_count"] == 0
    assert result["kinds_seen"] == {}
