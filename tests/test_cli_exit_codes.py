"""Tests for CLI help output and exit codes."""

import subprocess
import sys


def test_cli_help_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "famulix" in result.stdout.lower()


def test_cli_version_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1" in result.stdout


def test_cli_unknown_subcommand_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "nonexistent_command_xyz"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_cli_demo_help():
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "demo", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_cli_recall_help():
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "recall", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_cli_brief_help():
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "brief", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
