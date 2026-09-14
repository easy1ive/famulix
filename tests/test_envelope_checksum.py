"""Tests for envelope checksum integrity and round-trip verification."""

from famulix.envelope import Envelope


def test_checksum_deterministic():
    e1 = Envelope.wrap(kind="event", payload={"key": "value"})
    e2 = Envelope.wrap(kind="event", payload={"key": "value"})
    assert e1.checksum == e2.checksum


def test_checksum_changes_with_payload():
    e1 = Envelope.wrap(kind="event", payload={"key": "value_a"})
    e2 = Envelope.wrap(kind="event", payload={"key": "value_b"})
    assert e1.checksum != e2.checksum


def test_envelope_jsonl_roundtrip():
    e = Envelope.wrap(kind="note", payload={"text": "test content"})
    line = e.to_jsonl_line()
    restored = Envelope.from_jsonl_line(line)
    assert restored.kind == e.kind
    assert restored.checksum == e.checksum
    assert restored.payload == e.payload


def test_envelope_verify_valid():
    e = Envelope.wrap(kind="fact", payload={"data": [1, 2, 3]})
    assert e.verify() is True


def test_envelope_frozen():
    """Envelopes are immutable after creation."""
    import dataclasses

    import pytest

    e = Envelope.wrap(kind="fact", payload={"data": "original"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.payload = {"data": "tampered"}


def test_envelope_roundtrip_preserves_kind():
    e = Envelope.wrap(kind="memory_node", payload={"node_id": "abc"})
    line = e.to_jsonl_line()
    restored = Envelope.from_jsonl_line(line)
    assert restored.kind == "memory_node"
