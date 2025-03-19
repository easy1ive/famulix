"""Append-only SQLite event log with checksummed frames.

The event log is the source of truth. All projections (memory graph,
retrieval index, preference store) are rebuilt from the log.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from famulix.envelope import Envelope
from famulix.events import Event

LATEST_SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS event_log (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    envelope_json TEXT NOT NULL,
    checksum TEXT NOT NULL,
    inserted_at_s INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_event_log_id ON event_log(event_id);
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""


class EventLog:
    """Append-only event log backed by SQLite.

    Frames are envelope-encoded JSON. Each insert is a single transaction;
    the log can be replayed from seq 0 to rebuild any projection.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._txn() as cur:
            cur.executescript(SCHEMA_SQL)
            version_row = cur.execute("SELECT MAX(version) FROM schema_version").fetchone()
            version = int(version_row[0] or 1)
            if version > LATEST_SCHEMA_VERSION:
                raise RuntimeError(
                    f"event log schema {version} is newer than supported {LATEST_SCHEMA_VERSION}"
                )
            columns = {row[1] for row in cur.execute("PRAGMA table_info(event_log)")}
            if "source" not in columns:
                cur.execute("ALTER TABLE event_log ADD COLUMN source TEXT NOT NULL DEFAULT ''")
                frames = cur.execute("SELECT seq, envelope_json FROM event_log").fetchall()
                for seq, line in frames:
                    event = Event.from_envelope(Envelope.from_jsonl_line(line))
                    cur.execute(
                        "UPDATE event_log SET source = ? WHERE seq = ?", (event.source, seq)
                    )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_event_log_source ON event_log(source)")
            cur.execute("DELETE FROM schema_version")
            cur.execute("INSERT INTO schema_version(version) VALUES (?)", (LATEST_SCHEMA_VERSION,))

    @contextmanager
    def _txn(self) -> Iterator[sqlite3.Cursor]:
        cur = self._conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            yield cur
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cur.close()

    def append(self, event: Event, inserted_at_s: int) -> int:
        """Append an event. Returns its sequence number."""
        env = event.to_envelope()
        line = env.to_jsonl_line()
        with self._txn() as cur:
            cur.execute(
                "INSERT INTO event_log(event_id, envelope_json, checksum, inserted_at_s, source)"
                " VALUES (?, ?, ?, ?, ?)",
                (event.event_id, line, env.checksum, inserted_at_s, event.source),
            )
            return cur.lastrowid or 0

    def count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM event_log")
        return int(cur.fetchone()[0])

    def get_by_seq(self, seq: int) -> Event | None:
        cur = self._conn.execute(
            "SELECT envelope_json, checksum FROM event_log WHERE seq = ?", (seq,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._decode_frame(row[0], row[1])

    def get_by_id(self, event_id: str) -> Event | None:
        cur = self._conn.execute(
            "SELECT envelope_json, checksum FROM event_log WHERE event_id = ?", (event_id,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._decode_frame(row[0], row[1])

    def iter_events(self, start_seq: int = 1) -> Iterator[Event]:
        cur = self._conn.execute(
            "SELECT envelope_json, checksum FROM event_log WHERE seq >= ? ORDER BY seq",
            (start_seq,),
        )
        for row in cur:
            yield self._decode_frame(row[0], row[1])

    @staticmethod
    def _decode_frame(line: str, stored_checksum: str) -> Event:
        env = Envelope.from_jsonl_line(line)
        if env.checksum != stored_checksum:
            raise ValueError("event log frame checksum does not match stored checksum")
        return Event.from_envelope(env)

    def replay_into(self, other: EventLog) -> int:
        """Replay all events into another log. Returns count copied."""
        n = 0
        for evt in self.iter_events():
            other.append(evt, 0)
            n += 1
        return n

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> EventLog:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
