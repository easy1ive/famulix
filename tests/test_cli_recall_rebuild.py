"""Tests for recall --rebuild-index CLI flag."""

import subprocess
import sys


def test_recall_rebuild_index_runs():
    """recall --rebuild-index should run without error."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "recall",
            "meeting",
            "--rebuild-index",
            "-k",
            "5",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0


def test_recall_rebuild_with_diverse():
    """recall --rebuild-index --diverse should work together."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "recall",
            "important",
            "--rebuild-index",
            "--diverse",
            "-k",
            "3",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0


def test_recall_rebuild_json_output():
    """recall --rebuild-index --json should produce valid JSON."""
    import json

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "recall",
            "test",
            "--rebuild-index",
            "--json",
            "-k",
            "5",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "results" in data
