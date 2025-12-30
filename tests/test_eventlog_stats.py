"""Test eventlog statistics."""

import tempfile
from pathlib import Path

from famulix.eventlog import eventlog_stats


def test_nonexistent_log():
    """Nonexistent log should report exists=False."""
    result = eventlog_stats("/tmp/nonexistent_12345.jsonl")
    assert result["exists"] is False


def test_empty_log():
    """Empty log should have zero count."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        path = f.name
    try:
        result = eventlog_stats(path)
        assert result["exists"] is True
        assert result["count"] == 0
    finally:
        Path(path).unlink()


def test_log_with_entries():
    """Log with entries should count them."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        f.write('{"a": 1}\n')
        f.write('{"b": 2}\n')
        path = f.name
    try:
        result = eventlog_stats(path)
        assert result["count"] == 2
        assert result["size_bytes"] > 0
    finally:
        Path(path).unlink()
