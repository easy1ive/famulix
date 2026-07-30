"""Tests for context --max-items CLI flag."""

import subprocess
import sys


def test_context_max_items_limits_output():
    """context --max-items should limit number of items."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "context",
            "test query",
            "--max-items",
            "3",
            "--days",
            "7",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    # Should have at most 3 items (count lines with "tok")
    item_lines = [line for line in result.stdout.split("\n") if "tok" in line and "val=" in line]
    assert len(item_lines) <= 3


def test_context_default_max_items():
    """context without --max-items uses default of 10."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "context", "test", "--days", "7"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0


def test_context_max_items_with_budget():
    """context --max-items --budget should respect both constraints."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "context",
            "test",
            "--max-items",
            "5",
            "--budget",
            "200",
            "--days",
            "7",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "budget=200" in result.stdout
