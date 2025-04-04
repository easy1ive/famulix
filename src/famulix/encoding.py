"""Encoding pipeline: raw events into episodes, entities, and facts.

The pipeline is deterministic: same events in same order produce the same
memory graph. Rule-based extraction; no model calls in the base path.
"""

from __future__ import annotations

import re
from collections import defaultdict

from famulix.clock import day_start_epoch
from famulix.events import Event
from famulix.memory_graph import MemoryEdge, MemoryGraph, MemoryNode
from famulix.types import EntityId


def day_segment(events: list[Event], tz_offset_hours: int = 8) -> dict[str, list[Event]]:
    """Group events by local calendar day.

    Returns a dict mapping ISO date strings to event lists in temporal order.
    """
    buckets: dict[str, list[Event]] = defaultdict(list)
    for evt in sorted(events, key=lambda e: e.timestamp_s):
        from datetime import datetime, timedelta, timezone

        dt = datetime.fromtimestamp(evt.timestamp_s, tz=timezone(timedelta(hours=tz_offset_hours)))
        day = dt.date().isoformat()
        buckets[day].append(evt)
    return dict(buckets)


def build_episode_node(day: str, events: list[Event]) -> MemoryNode:
    """Build an episode node summarizing a day's events."""
    body_parts = []
    for evt in events:
        text = evt.data.get("text", "") or evt.data.get("title", "")
        body_parts.append(f"[{evt.event_type}] {text}")
    body = "\n".join(body_parts)
    return MemoryNode.create(
        "episode",
        f"Day {day} ({len(events)} events)",
        body,
        metadata={"day": day, "event_count": str(len(events))},
        created_at_s=day_start_epoch(day),
    )


DEFAULT_ALIASES: dict[str, list[str]] = {
    "alice": ["alice", "Alice", "爱丽丝"],
    "bob": ["bob", "Bob", "鲍勃"],
    "charlie": ["charlie", "Charlie", "查理"],
    "dave": ["dave", "Dave", "戴夫"],
}


def extract_entities(text: str, aliases: dict[str, list[str]] | None = None) -> list[EntityId]:
    """Rule-based entity mention extraction using an alias table.

    Returns matched entity ids in order of first appearance, deduplicated.
    """
    table = aliases or DEFAULT_ALIASES
    found: list[tuple[int, EntityId]] = []
    lowered = text.lower()
    for eid, alias_list in table.items():
        for alias in alias_list:
            idx = lowered.find(alias.lower())
            if idx >= 0:
                found.append((idx, eid))
                break
    found.sort(key=lambda x: x[0])
    seen: set[EntityId] = set()
    result: list[EntityId] = []
    for _, eid in found:
        if eid not in seen:
            seen.add(eid)
            result.append(eid)
    return result


def extract_fact_candidates(event: Event, min_confidence: float = 0.5) -> list[tuple[str, float]]:
    """Extract fact candidates from an event with confidence scores.

    This is a rule-based baseline: each sentence-clause pair becomes a
    candidate, weighted by commitment language and length.
    """
    return [
        (candidate, confidence)
        for candidate, confidence, _start, _end in extract_fact_candidate_spans(
            event, min_confidence
        )
    ]


def extract_fact_candidate_spans(
    event: Event, min_confidence: float = 0.5
) -> list[tuple[str, float, int, int]]:
    """Return candidate text, confidence, and exact source character offsets."""
    text = event.data.get("text", "") or event.data.get("title", "")
    if not text:
        return []
    commitment_markers = ["will", "must", "always", "never", "is a", "is the", "决定"]
    candidates: list[tuple[str, float, int, int]] = []
    clauses_seen = 0
    for match in re.finditer(r"[^.。]+", text):
        raw = match.group()
        leading = len(raw) - len(raw.lstrip())
        sent = raw.strip()
        if not sent:
            continue
        clauses_seen += 1
        if clauses_seen > 5:
            break
        conf = 0.5 + min(len(sent) / 400, 0.3)
        lowered = sent.lower()
        for marker in commitment_markers:
            if marker.lower() in lowered:
                conf += 0.1
                break
        conf = round(min(conf, 0.99), 6)
        if conf >= min_confidence:
            start = match.start() + leading
            candidates.append((sent, conf, start, start + len(sent)))
    return candidates


def decode_fact_candidate(event: Event, node: MemoryNode) -> str | None:
    """Reconstruct an encoded fact's source span when its event is available."""
    if node.kind != "fact" or node.metadata.get("source_event") != event.event_id:
        return None
    try:
        start = int(node.metadata["source_start"])
        end = int(node.metadata["source_end"])
    except (KeyError, ValueError):
        return None
    source = event.data.get("text", "") or event.data.get("title", "")
    if start < 0 or end < start or end > len(source):
        return None
    return source[start:end]


def encode_events_to_graph(
    events: list[Event],
    *,
    aliases: dict[str, list[str]] | None = None,
    tz_offset_hours: int = 8,
) -> MemoryGraph:
    """Run the full encoding pipeline: events -> memory graph.

    Produces episode nodes per day, entity nodes for detected mentions,
    fact candidates from note/message content, and edges linking them.
    """
    g = MemoryGraph()
    days = day_segment(events, tz_offset_hours)

    for day, day_events in days.items():
        ep = build_episode_node(day, day_events)
        g.add_node(ep)

        for evt in day_events:
            # Entity mentions
            text = evt.data.get("text", "") or evt.data.get("title", "")
            entities = extract_entities(text, aliases)
            for eid in entities:
                enode = MemoryNode.create(
                    "entity", eid, f"entity: {eid}", metadata={"entity_id": eid}
                )
                g.add_node(enode)
                g.add_edge(MemoryEdge.create(ep.node_id, enode.node_id, "mentions"))

            # Fact candidates
            for fact_text, conf, start, end in extract_fact_candidate_spans(evt):
                fnode = MemoryNode.create(
                    "fact",
                    fact_text[:60],
                    fact_text,
                    metadata={
                        "confidence": str(conf),
                        "source_event": evt.event_id,
                        "source_start": str(start),
                        "source_end": str(end),
                    },
                    created_at_s=evt.timestamp_s,
                )
                g.add_node(fnode)
                g.add_edge(MemoryEdge.create(fnode.node_id, ep.node_id, "part_of", weight=conf))
                g.add_edge(MemoryEdge.create(fnode.node_id, ep.node_id, "derived_from"))

    return g
