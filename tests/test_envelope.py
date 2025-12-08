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


def test_envelope_wrap_creates_checksummed_wrapper() -> None:
    from famulix.envelope import Envelope

    env = Envelope.wrap("note", {"text": "hello"})
    assert env.kind == "note"
    assert env.payload == {"text": "hello"}
    assert isinstance(env.checksum, str)
    assert len(env.checksum) > 0


def test_envelope_to_jsonl_roundtrip() -> None:
    from famulix.envelope import Envelope

    env = Envelope.wrap("event", {"data": "test"})
    line = env.to_jsonl_line()
    restored = Envelope.from_jsonl_line(line)
    assert restored.kind == env.kind
    assert restored.payload == env.payload
    assert restored.checksum == env.checksum


def test_envelope_checksum_deterministic() -> None:
    from famulix.envelope import Envelope

    env1 = Envelope.wrap("note", {"text": "same"})
    env2 = Envelope.wrap("note", {"text": "same"})
    assert env1.checksum == env2.checksum


def test_envelope_checksum_detects_tampering() -> None:
    from famulix.envelope import Envelope

    env1 = Envelope.wrap("note", {"text": "original"})
    env2 = Envelope.wrap("note", {"text": "tampered"})
    assert env1.checksum != env2.checksum


def test_envelope_rejects_empty_kind() -> None:
    import pytest

    from famulix.envelope import Envelope

    with pytest.raises(ValueError, match="non-empty"):
        Envelope.wrap("", {"data": "test"})


def test_validate_envelope_valid() -> None:
    from famulix.envelope import Envelope, validate_envelope

    env = Envelope.wrap("note", {"text": "hello"})
    problems = validate_envelope(env)
    assert problems == []


def test_validate_envelope_detects_problems() -> None:
    from famulix.envelope import Envelope, validate_envelope

    env = Envelope.wrap("note", {"text": "hello"})
    # Manually break it by replacing the frozen dataclass
    broken = Envelope(
        schema_version=env.schema_version,
        kind="",
        payload=env.payload,
        checksum=env.checksum,
    )
    problems = validate_envelope(broken)
    assert len(problems) >= 1
    assert any("kind" in p for p in problems)


def test_batch_verify_all_valid() -> None:
    from famulix.envelope import Envelope, batch_verify

    envelopes = [
        Envelope.wrap("note", {"text": "one"}),
        Envelope.wrap("note", {"text": "two"}),
    ]
    valid_count, errors = batch_verify(envelopes)
    assert valid_count == 2
    assert errors == []


def test_batch_verify_with_invalid() -> None:
    from famulix.envelope import Envelope, batch_verify

    env1 = Envelope.wrap("note", {"text": "valid"})
    env2_good = Envelope.wrap("note", {"text": "tampered"})
    env2 = Envelope(
        schema_version=env2_good.schema_version,
        kind=env2_good.kind,
        payload=env2_good.payload,
        checksum="wrong_checksum",
    )

    valid_count, errors = batch_verify([env1, env2])
    assert valid_count == 1
    assert len(errors) == 1


def test_envelope_statistics_empty() -> None:
    from famulix.envelope import envelope_statistics

    stats = envelope_statistics([])
    assert stats["count"] == 0
    assert stats["schema_versions"] == set()


def test_envelope_statistics_with_data() -> None:
    from famulix.envelope import Envelope, envelope_statistics

    env1 = Envelope.wrap("note", {"text": "one"})
    env2 = Envelope.wrap("note", {"text": "two"})
    stats = envelope_statistics([env1, env2])
    assert stats["count"] == 2
    assert len(stats["schema_versions"]) == 1
    assert "checksum_lengths" in stats
