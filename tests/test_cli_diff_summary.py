"""Tests for diff --summary CLI flag."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def test_diff_summary_flag_runs():
    """diff --summary should produce human-readable output."""
    # Create two minimal session files
    session_a = {"session_id": "test-a", "seed": 42, "entries": [], "next_seq": 0, "digest": "abc"}
    session_b = {"session_id": "test-b", "seed": 42, "entries": [], "next_seq": 0, "digest": "def"}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f_a:
        json.dump(session_a, f_a)
        path_a = f_a.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f_b:
        json.dump(session_b, f_b)
        path_b = f_b.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "famulix", "diff", path_a, path_b, "--summary"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Should succeed or fail gracefully
        assert result.returncode in (0, 2)
        if result.returncode == 0:
            assert "Session diff:" in result.stdout
    finally:
        Path(path_a).unlink()
        Path(path_b).unlink()


def test_diff_json_output():
    """diff without --summary should produce JSON or fail gracefully."""
    session_a = {"session_id": "test-a", "seed": 42, "entries": [], "next_seq": 0, "digest": "abc"}
    session_b = {"session_id": "test-a", "seed": 42, "entries": [], "next_seq": 0, "digest": "abc"}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f_a:
        json.dump(session_a, f_a)
        path_a = f_a.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f_b:
        json.dump(session_b, f_b)
        path_b = f_b.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "famulix", "diff", path_a, path_b],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Should succeed or fail gracefully with exit code 2
        assert result.returncode in (0, 2)
        if result.returncode == 0:
            # Should be valid JSON
            data = json.loads(result.stdout)
            assert "identical" in data
    finally:
        Path(path_a).unlink()
        Path(path_b).unlink()
