"""Initial test file."""

from __future__ import annotations

import famulix


def test_package_version() -> None:
    assert isinstance(famulix.__version__, str)
    parts = famulix.__version__.split(".")
    assert len(parts) == 3
