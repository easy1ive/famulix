"""Test JSON output modes for various CLI commands."""

import subprocess
import sys


def test_context_json_flag():
    """Verify context command accepts --json flag."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "context", "--json"],
        capture_output=True,
        text=True,
    )
    # Should not fail with argparse error
    assert result.returncode != 2


def test_prefs_json_flag():
    """Verify prefs command accepts --json flag."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "prefs", "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 2


def test_triggers_json_flag():
    """Verify triggers command accepts --json flag."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix.cli", "triggers", "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 2
