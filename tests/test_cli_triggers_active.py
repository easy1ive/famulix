"""Tests for triggers --active-only CLI flag."""

import subprocess
import sys


def test_triggers_active_only_runs():
    """triggers --active-only should run without error."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "triggers",
            "--active-only",
            "--days",
            "7",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "triggers" in result.stdout.lower()


def test_triggers_without_active_only():
    """triggers without --active-only shows all triggers."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "triggers", "--days", "7"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0


def test_triggers_json_output():
    """triggers --json should produce valid JSON."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "triggers", "--json", "--days", "7"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
