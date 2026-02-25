"""Test CLI version flag."""

import subprocess
import sys


def test_version_flag():
    """Verify --version prints version."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "0.1" in result.stdout


def test_help_flag():
    """Verify --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "famulix" in result.stdout
