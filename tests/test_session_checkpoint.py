"""Tests for session checkpoint and resume."""

import tempfile
from pathlib import Path

from famulix.session_checkpoint import Checkpoint, can_resume_from


def test_checkpoint_save_load_roundtrip():
    cp = Checkpoint(
        event_offset=100,
        state={"graph_nodes": 50, "memories": 30},
        checksum="abc123",
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = Path(f.name)

    cp.save(path)
    loaded = Checkpoint.load(path)

    assert loaded.event_offset == cp.event_offset
    assert loaded.state == cp.state

    path.unlink()


def test_can_resume_from_validates_offset():
    cp = Checkpoint(event_offset=50, state={}, checksum="x")

    assert can_resume_from(cp, 100)
    assert not can_resume_from(cp, 50)
    assert not can_resume_from(cp, 30)
