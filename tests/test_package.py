"""Package metadata and version consistency checks."""

from __future__ import annotations

import re
from pathlib import Path

import famulix


def test_package_version() -> None:
    assert isinstance(famulix.__version__, str)
    parts = famulix.__version__.split(".")
    assert len(parts) == 3


def test_version_matches_pyproject_and_changelog() -> None:
    """The declared, imported, and changelog versions must stay in sync."""
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    declared = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    assert declared is not None
    assert declared.group(1) == famulix.__version__
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    latest = re.search(r"^## \[([^\]]+)\]", changelog, re.MULTILINE)
    assert latest is not None
    assert latest.group(1) == famulix.__version__
