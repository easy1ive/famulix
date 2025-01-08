"""Tests for checksum and deterministic helpers."""

from __future__ import annotations

import json

from famulix.utils import content_checksum, content_id, stable_json_dumps


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
