"""Test prefs-report CLI subcommand."""

import subprocess
import sys


def test_prefs_report_help():
    """Verify prefs-report subcommand has help text."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "prefs-report", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "prefs-report" in result.stdout
    assert "--persona" in result.stdout
    assert "--seed" in result.stdout
    assert "--days" in result.stdout


def test_prefs_report_runs():
    """Verify prefs-report runs with default arguments."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "prefs-report", "--days", "7"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "# Preference Profile Report" in result.stdout
    assert "**Version**" in result.stdout
    assert "**Total entries**" in result.stdout
