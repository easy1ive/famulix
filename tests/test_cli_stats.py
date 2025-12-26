"""Test stats CLI command."""

import json
import subprocess
import sys


def test_stats_command_runs():
    """Verify stats command executes successfully."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "stats", "--days", "3"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Nodes:" in result.stdout


def test_stats_json_output():
    """Verify stats --json produces valid JSON."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "stats", "--days", "3", "--json"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "node_count" in data
    assert "edge_count" in data
    assert "kind_counts" in data
