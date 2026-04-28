"""Test exec-report CLI subcommand."""

import subprocess
import sys


def test_exec_report_help():
    """Verify exec-report subcommand has help text."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "exec-report", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "exec-report" in result.stdout


def test_exec_report_runs():
    """Verify exec-report runs and produces a report."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "exec-report"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "# Plan Execution Report" in result.stdout
    assert "## Summary" in result.stdout
    assert "**Steps completed**: 4" in result.stdout
    assert "**Successes**: 4" in result.stdout
    assert "**Failures**: 0" in result.stdout
