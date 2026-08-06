"""Tests for prefs --learned-only CLI flag."""

import subprocess
import sys


def test_prefs_learned_only_runs():
    """prefs --learned-only should run without error."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "prefs",
            "--learned-only",
            "--days",
            "7",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Learned preferences" in result.stdout


def test_prefs_without_learned_only():
    """prefs without --learned-only shows all preferences."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "prefs", "--days", "7"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0


def test_prefs_learned_only_json():
    """prefs --learned-only --json should work."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "prefs",
            "--learned-only",
            "--json",
            "--days",
            "7",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
