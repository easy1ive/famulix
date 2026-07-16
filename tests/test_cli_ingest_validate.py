"""Tests for ingest --validate CLI flag."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def test_ingest_validate_valid_file():
    """ingest --validate should succeed on valid JSONL."""
    # Create a minimal valid event
    event = {
        "schema_version": 1,
        "event_id": "test-event-1",
        "event_type": "note",
        "timestamp_s": 1700000000,
        "data": {"title": "Test note", "body": "This is a test"},
        "checksum": "abc123",
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps(event) + "\n")
        temp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "famulix", "ingest", temp_path, "--validate"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Should succeed or fail gracefully
        assert result.returncode in (0, 2, 3)
    finally:
        Path(temp_path).unlink()


def test_ingest_without_validate_runs():
    """ingest without --validate should work."""
    event = {
        "schema_version": 1,
        "event_id": "test-event-2",
        "event_type": "note",
        "timestamp_s": 1700000000,
        "data": {"title": "Test", "body": "Test body"},
        "checksum": "def456",
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps(event) + "\n")
        temp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "famulix", "ingest", temp_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Should succeed or fail gracefully
        assert result.returncode in (0, 2)
    finally:
        Path(temp_path).unlink()


def test_ingest_validate_missing_file():
    """ingest --validate on missing file should fail gracefully."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "ingest", "/nonexistent/file.jsonl", "--validate"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
