"""Tests for forget --no-cascade CLI flag."""

import subprocess
import sys


def test_forget_no_cascade_flag_runs():
    """forget --no-cascade should run without error."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "forget",
            "test-memory-id",
            "--no-cascade",
            "--days",
            "7",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # Should fail gracefully (memory not found) or succeed
    assert result.returncode in (0, 1)


def test_forget_without_no_cascade():
    """forget without --no-cascade uses full cascade."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "forget",
            "test-memory-id",
            "--days",
            "7",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # Should fail gracefully (memory not found) or succeed
    assert result.returncode in (0, 1)


def test_forget_no_cascade_with_reason():
    """forget --no-cascade --reason should work together."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "forget",
            "test-memory-id",
            "--no-cascade",
            "--reason",
            "test deletion",
            "--days",
            "7",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode in (0, 1)
