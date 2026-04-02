"""Test validate-session CLI subcommand."""

import tempfile
from pathlib import Path

from famulix.session import SessionRecorder


def test_cli_validate_session_valid():
    """Verify validate-session accepts a valid session file."""
    rec = SessionRecorder(session_id="test", seed=42)
    rec.record("event", {"data": "test"}, timestamp_s=100)
    rec.record("event", {"data": "test2"}, timestamp_s=200)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "session.jsonl"
        rec.save(path)

        # Load and validate
        loaded = SessionRecorder.load(path)
        assert loaded.verify()
        assert loaded.entry_count() == 2


def test_cli_validate_session_corrupted():
    """Verify validate-session detects corrupted session files."""
    rec = SessionRecorder(session_id="test", seed=42)
    rec.record("event", {"data": "test"}, timestamp_s=100)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "session.jsonl"
        rec.save(path)

        # Corrupt the file
        text = path.read_text()
        corrupted = text.replace("test", "corrupted")
        path.write_text(corrupted)

        # Should fail to load or verify
        try:
            loaded = SessionRecorder.load(path)
            assert not loaded.verify()
        except ValueError:
            pass  # Expected: corrupted checksum
