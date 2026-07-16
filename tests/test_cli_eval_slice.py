"""Tests for eval --slice CLI flag."""

import subprocess
import sys


def test_eval_slice_flag_runs():
    """eval --slice should run without error."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "eval",
            "--slice",
            "recall",
            "--days",
            "7",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0


def test_eval_multiple_slices():
    """eval --slice can be repeated for multiple slices."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "eval",
            "--slice",
            "recall",
            "--slice",
            "precision",
            "--days",
            "7",
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    import json

    data = json.loads(result.stdout)
    # Slices should be filtered to only recall and precision
    if "slices" in data:
        for key in data["slices"]:
            assert key in ("recall", "precision")


def test_eval_without_slice_shows_all():
    """eval without --slice shows all metrics."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "eval", "--days", "7"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    assert "recall_at_k" in result.stdout or "recall" in result.stdout
