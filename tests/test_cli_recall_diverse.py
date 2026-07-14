"""Tests for recall --diverse CLI flag."""

import subprocess
import sys


def test_recall_diverse_flag_runs():
    """recall --diverse should run without error."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "recall",
            "meeting",
            "--diverse",
            "-k",
            "5",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "meeting" in result.stdout.lower() or "results" in result.stdout.lower()


def test_recall_diverse_json_output():
    """recall --diverse --json should produce valid JSON."""
    import json

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "recall",
            "important",
            "--diverse",
            "--json",
            "-k",
            "3",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "results" in data
    assert len(data["results"]) <= 3


def test_recall_without_diverse_still_works():
    """recall without --diverse should work as before."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "recall", "test", "-k", "5"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
