"""Test eventlog schema migration v3 to v4 (content_hash column)."""

import sqlite3

from famulix.eventlog import LATEST_SCHEMA_VERSION, EventLog


def test_latest_schema_is_v4():
    assert LATEST_SCHEMA_VERSION == 4


def test_new_log_has_content_hash_column(tmp_path):
    log = EventLog(str(tmp_path / "test.db"))
    log.close()
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    columns = {row[1] for row in conn.execute("PRAGMA table_info(event_log)")}
    conn.close()
    assert "content_hash" in columns
    assert "metadata_json" in columns


def test_new_log_schema_version():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        log = EventLog(f"{tmp}/test.db")
        assert log.schema_version() == 4
        log.close()
