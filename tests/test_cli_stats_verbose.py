"""Tests for stats --verbose CLI flag."""

import subprocess
import sys


def test_stats_verbose_runs():
    """stats --verbose should run without error."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "stats", "--verbose", "--days", "7"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Edge kinds:" in result.stdout
    # Sample nodes section appears when there are nodes
    if "Sample nodes:" in result.stdout:
        assert "metadata:" in result.stdout or "[" in result.stdout


def test_stats_without_verbose():
    """stats without --verbose shows basic stats only."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "stats", "--days", "7"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Node kinds:" in result.stdout
    # Should not have verbose sections
    assert "Edge kinds:" not in result.stdout


def test_stats_verbose_json():
    """stats --verbose --json should work (verbose ignored for JSON)."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "stats", "--verbose", "--json", "--days", "7"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    import json

    data = json.loads(result.stdout)
    assert "node_count" in data
