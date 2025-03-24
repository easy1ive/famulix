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
