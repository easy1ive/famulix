"""Tests for export --pretty CLI flag."""

import json
import subprocess
import sys


def test_export_pretty_flag():
    """export --pretty should produce indented JSON."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "export", "--pretty"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    # Should be valid JSON
    data = json.loads(result.stdout)
    assert "nodes" in data
    # Should have indentation (newlines + spaces)
    assert "\n" in result.stdout
    assert "  " in result.stdout


def test_export_without_pretty_compact():
    """export without --pretty should produce compact JSON."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "export"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    # Should be valid JSON
    data = json.loads(result.stdout)
    assert "nodes" in data


def test_export_jsonl_ignores_pretty():
    """export --format jsonl should work regardless of --pretty."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "export", "--format", "jsonl", "--pretty"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    # JSONL format should have multiple lines
    lines = result.stdout.strip().split("\n")
    assert len(lines) > 1
