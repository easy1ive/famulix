"""Tests for checksum and deterministic helpers."""

from __future__ import annotations

import json

import pytest

from famulix.utils import (
    content_checksum,
    content_id,
    stable_hash,
    stable_json_dumps,
    truncate_string,
)


def test_content_checksum_deterministic() -> None:
    data = b"hello world"
    assert content_checksum(data) == content_checksum(data)


def test_content_checksum_different_inputs() -> None:
    assert content_checksum(b"a") != content_checksum(b"b")


def test_stable_json_sorts_keys() -> None:
    a = {"b": 2, "a": 1, "c": 3}
    b = {"c": 3, "b": 2, "a": 1}
    assert stable_json_dumps(a) == stable_json_dumps(b)


def test_stable_json_round_trip_strings() -> None:
    obj = {"name": "李雷", "tags": ["x", "y"], "n": 42}
    text = stable_json_dumps(obj)
    assert json.loads(text) == obj


def test_content_id_format() -> None:
    cid = content_id("evt", "some payload")
    assert cid.startswith("evt_")
    assert len(cid) == len("evt_") + 24


def test_content_id_deterministic() -> None:
    assert content_id("evt", "hello") == content_id("evt", "hello")
    assert content_id("evt", "hello") != content_id("evt", "world")


def test_stable_hash_deterministic() -> None:
    assert stable_hash("hello") == stable_hash("hello")
    assert stable_hash("hello") != stable_hash("world")


def test_stable_hash_length() -> None:
    assert len(stable_hash("test", length=8)) == 8
    assert len(stable_hash("test", length=16)) == 16


def test_stable_hash_rejects_zero_length() -> None:
    with pytest.raises(ValueError, match="positive"):
        stable_hash("test", length=0)


def test_truncate_string_short_unchanged() -> None:
    assert truncate_string("hello", 10) == "hello"


def test_truncate_string_adds_suffix() -> None:
    result = truncate_string("hello world", 8)
    assert len(result) == 8
    assert result.endswith("...")


def test_truncate_string_custom_suffix() -> None:
    result = truncate_string("abcdefgh", 5, suffix="~")
    assert result == "abcd~"
    assert len(result) == 5


def test_truncate_string_rejects_negative_max_len() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        truncate_string("x", -1)


def test_stable_json_dumps_sorts_keys() -> None:
    from famulix.utils import stable_json_dumps

    data = {"z": 1, "a": 2, "m": 3}
    result = stable_json_dumps(data)
    assert result == '{"a":2,"m":3,"z":1}'


def test_stable_json_dumps_deterministic() -> None:
    from famulix.utils import stable_json_dumps

    data = {"key": "value", "number": 42}
    result1 = stable_json_dumps(data)
    result2 = stable_json_dumps(data)
    assert result1 == result2


def test_stable_hash_produces_consistent_output() -> None:
    from famulix.utils import stable_hash

    text = "hello world"
    hash1 = stable_hash(text)
    hash2 = stable_hash(text)
    assert hash1 == hash2
    assert len(hash1) > 0


def test_stable_hash_detects_changes() -> None:
    from famulix.utils import stable_hash

    hash1 = stable_hash("original")
    hash2 = stable_hash("modified")
    assert hash1 != hash2


def test_truncate_string_respects_max_length() -> None:
    from famulix.utils import truncate_string

    long_text = "a" * 100
    truncated = truncate_string(long_text, max_len=50)
    assert len(truncated) <= 50
    assert truncated.endswith("...")


def test_truncate_string_preserves_short_text() -> None:
    from famulix.utils import truncate_string

    short_text = "hello"
    result = truncate_string(short_text, max_len=50)
    assert result == short_text
