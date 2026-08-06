"""Tests for brief --no-metadata CLI flag."""

import subprocess
import sys


def test_brief_no_metadata_flag_runs():
    """brief --no-metadata should run without error."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "brief",
            "--no-metadata",
            "--days",
            "7",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    # Should not have metadata lines
    assert "Run metadata:" not in result.stdout


def test_brief_without_no_metadata():
    """brief without --no-metadata includes metadata."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "brief", "--days", "7"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0


def test_brief_no_metadata_with_section():
    """brief --no-metadata --section should work together."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "brief",
            "--no-metadata",
            "--section",
            "agenda",
            "--days",
            "7",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
