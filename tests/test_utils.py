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
