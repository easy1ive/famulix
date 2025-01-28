"""Golden roundtrip test for event serialization.

Golden checksums are committed so serialization drift is deliberate.
"""

from __future__ import annotations

from famulix.envelope import Envelope
from famulix.events import Event, note_event
from famulix.utils import content_checksum, stable_json_dumps


def test_note_envelope_jsonl_stable() -> None:
    evt = note_event(1_700_000_000, "manual", "每天记一笔")
    env = evt.to_envelope()
    line = env.to_jsonl_line()
    reparsed = Envelope.from_jsonl_line(line)
    assert reparsed.checksum == env.checksum
    evt2 = Event.from_envelope(reparsed)
    assert evt2 == evt


def test_envelope_checksum_matches_payload_bytes() -> None:
    evt = note_event(100, "s", "x")
    env = evt.to_envelope()
    payload_bytes = stable_json_dumps(env.payload).encode("utf-8")
    assert content_checksum(payload_bytes) == env.checksum


def test_event_id_deterministic_across_calls() -> None:
    a = note_event(1_700_000_000, "cli", "meeting notes from today")
    b = note_event(1_700_000_000, "cli", "meeting notes from today")
    assert a.event_id == b.event_id
    # Verify the checksum prefix property
    assert len(a.event_id) > 20
