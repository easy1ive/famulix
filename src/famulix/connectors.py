"""Offline connector records for deterministic personal-data ingestion."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol

from famulix.events import Event, EventType
from famulix.utils import stable_json_dumps

ConnectorKind = Literal["note", "message", "calendar", "file"]


@dataclass(frozen=True)
class ConnectorRecord:
    """A normalized item emitted by an offline connector."""

    source: str
    external_id: str
    kind: ConnectorKind
    timestamp_s: int
    title: str
    body: str

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.external_id.strip():
            raise ValueError("source and external_id must be non-empty")
        if self.timestamp_s < 0:
            raise ValueError("timestamp_s must be non-negative")


@dataclass(frozen=True)
class ConnectorBatch:
    """Versioned, checksummed output from one connector source."""

    source: str
    records: tuple[ConnectorRecord, ...]
    schema_version: int
    checksum: str

    @classmethod
    def create(cls, source: str, records: list[ConnectorRecord]) -> ConnectorBatch:
        if not source.strip():
            raise ValueError("source must be non-empty")
        if any(record.source != source for record in records):
            raise ValueError("every record must belong to the batch source")
        ordered = tuple(sorted(records, key=lambda item: (item.timestamp_s, item.external_id)))
        payload = stable_json_dumps(
            {"source": source, "schema_version": 1, "records": [asdict(item) for item in ordered]}
        )
        return cls(
            source=source,
            records=ordered,
            schema_version=1,
            checksum=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        )

    def verify(self) -> bool:
        expected = ConnectorBatch.create(self.source, list(self.records))
        return self.schema_version == expected.schema_version and self.checksum == expected.checksum


class OfflineConnector(Protocol):
    """Small protocol implemented by deterministic local connectors."""

    @property
    def source(self) -> str: ...

    def collect(self) -> ConnectorBatch: ...


@dataclass(frozen=True)
class ScriptedConnector:
    """Connector backed by an explicit synthetic record list."""

    source: str
    records: tuple[ConnectorRecord, ...]

    def collect(self) -> ConnectorBatch:
        return ConnectorBatch.create(self.source, list(self.records))


class ConnectorHub:
    """Collect and normalize records from a deterministic connector set."""

    def __init__(self, connectors: list[OfflineConnector]) -> None:
        names = [connector.source for connector in connectors]
        if len(names) != len(set(names)):
            raise ValueError("connector sources must be unique")
        self.connectors = tuple(sorted(connectors, key=lambda connector: connector.source))

    def collect(self) -> tuple[ConnectorBatch, ...]:
        batches = tuple(connector.collect() for connector in self.connectors)
        if any(not batch.verify() for batch in batches):
            raise ValueError("connector returned an invalid batch checksum")
        return batches

    def collect_partial(self) -> tuple[tuple[ConnectorBatch, ...], tuple[str, ...]]:
        """Collect tolerating ConnectorError; returns (batches, failed_sources).

        Batches keep deterministic source ordering and are checksum-verified;
        connector failures are reported per source instead of aborting the
        sweep. Unexpected exceptions still propagate.
        """
        batches: list[ConnectorBatch] = []
        failed: list[str] = []
        for connector in self.connectors:
            try:
                batch = connector.collect()
            except ConnectorError:
                failed.append(connector.source)
                continue
            if not batch.verify():
                raise ValueError("connector returned an invalid batch checksum")
            batches.append(batch)
        return tuple(batches), tuple(failed)

    def records(self) -> list[ConnectorRecord]:
        by_identity: dict[tuple[str, str], ConnectorRecord] = {}
        for batch in self.collect():
            for record in batch.records:
                key = (record.source, record.external_id)
                existing = by_identity.get(key)
                if existing is not None and existing != record:
                    raise ValueError(
                        f"conflicting connector record: {record.source}/{record.external_id}"
                    )
                by_identity[key] = record
        return sorted(
            by_identity.values(), key=lambda item: (item.timestamp_s, item.source, item.external_id)
        )

    def source_count(self) -> int:
        return len(self.connectors)

    def sources(self) -> list[str]:
        return [connector.source for connector in self.connectors]

    def record_count(self) -> int:
        return len(self.records())

    def to_events(self) -> list[Event]:
        """Convert normalized records to deterministic versioned events."""
        events: list[Event] = []
        for record in self.records():
            if record.kind == "note":
                data: dict[str, Any] = {"text": record.body}
                kind: EventType = "note"
            elif record.kind == "message":
                data = {"direction": "in", "counterpart": record.title, "text": record.body}
                kind = "message"
            elif record.kind == "calendar":
                data = {
                    "title": record.title,
                    "description": record.body,
                    "start_s": record.timestamp_s,
                    "end_s": record.timestamp_s,
                    "attendees": [],
                }
                kind = "calendar_item"
            else:
                data = {"path": record.title, "action": record.body}
                kind = "file_touch"
            events.append(Event.create(kind, record.timestamp_s, record.source, data))
        return events


class ConnectorError(RuntimeError):
    """Raised when a connector fails during collection."""

    def __init__(self, source: str, message: str = "") -> None:
        super().__init__(message or f"connector failed: {source}")
        self.source = source


class FlakyConnector:
    """Deterministic failure injection around a working connector.

    Every ``fail_every``-th call to :meth:`collect` raises ConnectorError.
    The schedule comes from a call counter — never from wall-clock time or
    randomness — so tests reproduce the exact failure pattern.
    """

    def __init__(self, inner: OfflineConnector, fail_every: int = 3) -> None:
        if fail_every < 2:
            raise ValueError("fail_every must be at least 2")
        self.inner = inner
        self.fail_every = fail_every
        self.calls = 0

    @property
    def source(self) -> str:
        return self.inner.source

    def collect(self) -> ConnectorBatch:
        self.calls += 1
        if self.calls % self.fail_every == 0:
            raise ConnectorError(self.source)
        return self.inner.collect()


def validate_connector_batch(batch: ConnectorBatch) -> list[str]:
    """Validate a connector batch for consistency.

    Checks:
    - Source is non-empty
    - All records have the same source
    - All records have valid timestamps
    - Checksum is valid

    Returns a list of validation problems found.
    """
    problems: list[str] = []

    if not batch.source or not batch.source.strip():
        problems.append("batch source is empty")

    for i, record in enumerate(batch.records):
        if record.source != batch.source:
            problems.append(
                f"record[{i}] source '{record.source}' != batch source '{batch.source}'"
            )
        if record.timestamp_s < 0:
            problems.append(f"record[{i}] has negative timestamp {record.timestamp_s}")
        if not record.title or not record.title.strip():
            problems.append(f"record[{i}] has empty title")

    if not batch.verify():
        problems.append("batch checksum verification failed")

    return problems


def connector_hub_diagnostics(hub: ConnectorHub) -> dict[str, object]:
    """Generate diagnostics for a connector hub.

    Returns a dict with:
    - connector_count: number of connectors
    - sources: list of source names
    - total_records: total records across all batches
    - per_source_counts: record count per source
    """
    batches = hub.collect()
    total_records = sum(len(b.records) for b in batches)
    per_source: dict[str, int] = {}
    for batch in batches:
        per_source[batch.source] = len(batch.records)

    return {
        "connector_count": len(batches),
        "sources": [b.source for b in batches],
        "total_records": total_records,
        "per_source_counts": per_source,
    }


def connectors_info() -> dict[str, object]:
    """Return info about connectors module."""
    return {"module": "connectors", "version": "0.1.2"}
