"""Tests for remember --confidence and --tags CLI flags."""

import subprocess
import sys


def test_remember_with_confidence():
    """remember --confidence should set confidence metadata."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "remember",
            "Test fact",
            "This is a test",
            "--confidence",
            "0.95",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Memory id:" in result.stdout
    assert "Confidence: 0.95" in result.stdout


def test_remember_with_tags():
    """remember --tags should set tag metadata."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "remember",
            "Meeting note",
            "Discuss project",
            "--tags",
            "work",
            "meeting",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Tags:" in result.stdout
    assert "work" in result.stdout
    assert "meeting" in result.stdout


def test_remember_with_both_flags():
    """remember --confidence --tags should work together."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "remember",
            "Important fact",
            "Critical information",
            "--confidence",
            "0.9",
            "--tags",
            "important",
            "critical",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Confidence: 0.90" in result.stdout
    assert "Tags:" in result.stdout


def test_remember_default_confidence():
    """remember without --confidence uses default 0.8."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "famulix",
            "remember",
            "Simple fact",
            "Simple body",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    # Should not print confidence when using default
    assert "Confidence:" not in result.stdout
