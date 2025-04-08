"""Tests for schema-versioned envelopes."""

from __future__ import annotations

import pytest

from famulix.envelope import Envelope


def test_wrap_and_verify_round_trip() -> None:
    payload = {"id": "x", "title": "hello", "n": 42}
    env = Envelope.wrap("event", payload)
    assert env.schema_version >= 1
    assert env.kind == "event"
    assert env.verify() is True


def test_from_dict_rejects_bad_checksum() -> None:
    data = {
        "schemaVersion": 1,
        "kind": "event",
        "payload": {"a": 1},
        "checksum": "deadbeef",
    }
    with pytest.raises(ValueError, match="checksum mismatch"):
        Envelope.from_dict(data)


def test_to_dict_round_trip() -> None:
    env = Envelope.wrap("memory", {"key": "value", "n": [1, 2, 3]})
    data = env.to_dict()
    env2 = Envelope.from_dict(data)
    assert env == env2


def test_jsonl_line_round_trip() -> None:
    env = Envelope.wrap("event", {"type": "note", "text": "你好"})
    line = env.to_jsonl_line()
    env2 = Envelope.from_jsonl_line(line)
    assert env == env2


def test_key_order_does_not_affect_checksum() -> None:
    a = Envelope.wrap("evt", {"b": 2, "a": 1, "c": 3})
    b = Envelope.wrap("evt", {"c": 3, "a": 1, "b": 2})
    assert a.checksum == b.checksum


def test_payload_mutation_detected() -> None:
    env = Envelope.wrap("evt", {"value": 1})
    data = env.to_dict()
    data["payload"]["value"] = 2
    with pytest.raises(ValueError):
        Envelope.from_dict(data)


@pytest.mark.parametrize(
    "data",
    [
        {"schemaVersion": 2, "kind": "event", "payload": {}, "checksum": "x"},
        {"schemaVersion": True, "kind": "event", "payload": {}, "checksum": "x"},
        {"schemaVersion": 1, "kind": "event", "payload": [], "checksum": "x"},
        {
            "schemaVersion": 1,
            "kind": "event",
            "payload": {},
            "checksum": "x",
            "extra": 1,
        },
    ],
)
def test_envelope_rejects_unsupported_schema_and_shapes(data: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        Envelope.from_dict(data)


def test_envelope_jsonl_rejects_nonstandard_numbers() -> None:
    with pytest.raises(ValueError, match="non-standard JSON"):
        Envelope.from_jsonl_line(
            '{"schemaVersion":1,"kind":"event","payload":{"n":NaN},"checksum":"x"}'
        )


def test_envelope_wrap_rejects_non_json_payload_values() -> None:
    with pytest.raises(ValueError):
        Envelope.wrap("event", {"number": float("inf")})
