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
