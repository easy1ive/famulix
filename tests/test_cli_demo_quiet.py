"""Tests for demo --quiet CLI flag."""

import subprocess
import sys


def test_demo_quiet_flag_runs():
    """demo --quiet should run without error."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "demo", "--quiet", "--days", "7"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    # Should not have the header line
    assert "famulix demo —" not in result.stdout
    # Should still have metrics
    assert "Recall@5:" in result.stdout


def test_demo_without_quiet():
    """demo without --quiet shows header."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "demo", "--days", "7"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    assert "famulix demo —" in result.stdout


def test_demo_quiet_with_json():
    """demo --quiet --json should work (quiet ignored for JSON)."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "demo", "--quiet", "--json", "--days", "7"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    import json

    data = json.loads(result.stdout)
    assert "persona_id" in data
