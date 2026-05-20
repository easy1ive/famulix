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


def validate_alias_table(aliases: dict[str, list[str]]) -> list[str]:
    """Validate an alias table and return any problems found.

    Rules:
    - Entity ids must be non-empty strings.
    - Each entity must have at least one alias.
    - Aliases must be non-empty strings.
    - No alias may appear under multiple entity ids (ambiguity).
    """
    problems: list[str] = []
    seen_aliases: dict[str, str] = {}

    for eid, alias_list in aliases.items():
        if not isinstance(eid, str) or not eid.strip():
            problems.append(f"entity id must be a non-empty string, got {eid!r}")
            continue
        if not isinstance(alias_list, list) or not alias_list:
            problems.append(f"entity {eid!r} must have at least one alias")
            continue
        for alias in alias_list:
            if not isinstance(alias, str) or not alias.strip():
                problems.append(f"entity {eid!r} has invalid alias: {alias!r}")
                continue
            normalized = alias.lower().strip()
            if normalized in seen_aliases and seen_aliases[normalized] != eid:
                other = seen_aliases[normalized]
                problems.append(f"alias {alias!r} appears under both {eid!r} and {other!r}")
            else:
                seen_aliases[normalized] = eid

    return problems


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
    payload = event.data.get("text", "") or event.data.get("title", "")
    if not isinstance(payload, str):
        return None
    source: str = payload
    if start < 0 or end < start or end > len(source):
        return None
    return source[start:end]


def _text_overlap(a: str, b: str) -> float:
    """Token Jaccard overlap for deduping fact candidates."""
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def dedupe_fact_candidates(
    candidates: list[tuple[str, float, int, int]],
    *,
    threshold: float = 0.7,
) -> list[tuple[str, float, int, int]]:
    """Remove near-duplicate fact candidates based on token overlap.

    Keeps the earlier-occurring (lower start index) candidate when two
    candidates overlap above the threshold. Stable ordering.
    """
    kept: list[tuple[str, float, int, int]] = []
    for cand in sorted(candidates, key=lambda c: c[2]):  # sort by start position
        is_dup = False
        for existing in kept:
            if _text_overlap(cand[0], existing[0]) >= threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(cand)
    return kept


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


def sanitize_hostile_text(text: str) -> str:
    """Sanitize text that may contain hostile or malformed content.

    Removes:
    - Zero-width characters (U+200B, U+200C, U+200D, U+FEFF)
    - Control characters except newline, tab, carriage return
    - Surrogate pairs (invalid UTF-16 sequences)
    - Excessive whitespace (collapse to single space)
    """
    import re
    import unicodedata

    result = []
    for char in text:
        code = ord(char)
        if code in (0x200B, 0x200C, 0x200D, 0xFEFF):
            continue
        if code < 0x20 and code not in (0x09, 0x0A, 0x0D):
            continue
        if 0xD800 <= code <= 0xDFFF:
            continue
        result.append(char)

    cleaned = "".join(result)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)

    return unicodedata.normalize("NFC", cleaned)


def segment_unicode_words(text: str) -> list[str]:
    """Segment text into words respecting unicode boundaries.

    Handles CJK characters, emoji, and combining marks correctly.
    CJK characters are treated as individual words.
    """
    import unicodedata

    normalized = unicodedata.normalize("NFC", text)

    tokens: list[str] = []
    current: list[str] = []

    for char in normalized:
        cat = unicodedata.category(char)
        name = unicodedata.name(char, "")

        is_cjk = "CJK" in name or "IDEOGRAPH" in name
        if is_cjk:
            if current:
                tokens.append("".join(current))
                current = []
            tokens.append(char)
        elif cat.startswith("L") or cat.startswith("N"):
            current.append(char)
        else:
            if current:
                tokens.append("".join(current))
                current = []
            if not char.isspace() and cat.startswith("P"):
                tokens.append(char)

    if current:
        tokens.append("".join(current))

    return tokens


def encoding_stats(graph: MemoryGraph) -> dict[str, object]:
    """Return encoding statistics for a memory graph."""
    return {
        "episode_count": len(graph.nodes_by_kind("episode")),
        "entity_count": len(graph.nodes_by_kind("entity")),
        "fact_count": len(graph.nodes_by_kind("fact")),
    }
