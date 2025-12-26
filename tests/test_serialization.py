"""Tests for serialization utilities."""

import json
from dataclasses import dataclass
from datetime import date, datetime

from famulix.serialization import from_json, to_json


@dataclass
class SampleData:
    name: str
    value: int


def test_encoder_handles_dataclass():
    """Verify encoder serializes dataclasses."""
    data = SampleData(name="test", value=42)
    result = json.loads(to_json(data))
    assert result == {"name": "test", "value": 42}


def test_encoder_handles_datetime():
    """Verify encoder handles datetime objects."""
    dt = datetime(2026, 11, 12, 10, 30, 0)
    result = to_json({"timestamp": dt})
    assert "2026-11-12T10:30:00" in result


def test_encoder_handles_date():
    """Verify encoder handles date objects."""
    d = date(2026, 11, 12)
    result = to_json({"date": d})
    assert "2026-11-12" in result


def test_encoder_handles_set():
    """Verify encoder converts sets to sorted lists."""
    result = json.loads(to_json({"items": {3, 1, 2}}))
    assert result == {"items": [1, 2, 3]}


def test_encoder_handles_bytes():
    """Verify encoder converts bytes to hex."""
    result = json.loads(to_json({"data": b"\x00\xff"}))
    assert result == {"data": "00ff"}


def test_roundtrip_simple():
    """Verify simple roundtrip serialization."""
    original = {"name": "test", "value": 42, "nested": {"a": 1}}
    assert from_json(to_json(original)) == original


def test_indent_formatting():
    """Verify indent parameter works."""
    result = to_json({"a": 1}, indent=2)
    assert "\n" in result
    assert "  " in result
