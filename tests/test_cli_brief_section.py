"""Tests for brief --section CLI flag."""

import subprocess
import sys


def test_brief_section_agenda():
    """brief --section agenda should output only agenda section."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "brief",
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
    # Should contain agenda-related content
    assert "agenda" in result.stdout.lower() or "no agenda" in result.stdout.lower()


def test_brief_section_reminders():
    """brief --section reminders should output only reminders."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "brief",
            "--section",
            "reminders",
            "--days",
            "7",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0


def test_brief_without_section_shows_all():
    """brief without --section shows full briefing."""
    result = subprocess.run(
        [sys.executable, "-m", "famulix", "brief", "--days", "7"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    # Should have multiple sections
    assert len(result.stdout) > 100
