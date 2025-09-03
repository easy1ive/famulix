"""Tests for the encoding pipeline."""

from __future__ import annotations

from famulix.encoding import (
    day_segment,
    decode_fact_candidate,
    encode_events_to_graph,
    extract_entities,
    extract_fact_candidate_spans,
    extract_fact_candidates,
)
from famulix.events import message_event, note_event
from famulix.memory_graph import MemoryNode


def test_day_segment_groups_by_local_day() -> None:
    # 2023-11-14 23:30 UTC = 2023-11-15 07:30 UTC+8
    # 2023-11-15 00:30 UTC = 2023-11-15 08:30 UTC+8
    e1 = note_event(1_700_000_000, "s", "a")  # 2023-11-14T22:13:20Z
    e2 = note_event(1_700_000_000 + 86400, "s", "b")  # +1 day
    days = day_segment([e1, e2], tz_offset_hours=8)
    assert len(days) == 2


def test_day_segment_same_day() -> None:
    e1 = note_event(1_700_000_000, "s", "a")
    e2 = note_event(1_700_000_000 + 3600, "s", "b")
    days = day_segment([e1, e2], tz_offset_hours=0)
    assert len(days) == 1
    the_day = next(iter(days))
    assert len(days[the_day]) == 2


def test_extract_entities_case_insensitive() -> None:
    result = extract_entities("Alice and Bob had a meeting")
    assert "alice" in result
    assert "bob" in result


def test_extract_entities_chinese_aliases() -> None:
    result = extract_entities("爱丽丝和鲍勃开会")
    assert "alice" in result
    assert "bob" in result


def test_extract_entities_ordered_by_first_appearance() -> None:
    result = extract_entities("Bob called Alice")
    assert result.index("bob") < result.index("alice")


def test_extract_entities_deduplicated() -> None:
    result = extract_entities("Alice alice ALICE")
    assert result.count("alice") == 1


def test_extract_entities_custom_aliases() -> None:
    aliases = {"project_x": ["Project X", "项目X"]}
    result = extract_entities("项目X 启动了", aliases)
    assert "project_x" in result


def test_extract_fact_candidates_returns_confidence() -> None:
    evt = note_event(100, "s", "Alice will attend the meeting tomorrow")
    candidates = extract_fact_candidates(evt)
    assert len(candidates) >= 1
    for text, conf in candidates:
        assert 0.0 < conf <= 1.0
        assert len(text) > 0


def test_extract_fact_candidates_empty_text() -> None:
    from famulix.events import Event

    evt = Event.create("file_touch", 100, "fs", {"path": "/x"})
    assert extract_fact_candidates(evt) == []


def test_extract_fact_candidates_respects_threshold() -> None:
    evt = note_event(100, "s", "short")
    all_candidates = extract_fact_candidates(evt, min_confidence=0.0)
    high_threshold = extract_fact_candidates(evt, min_confidence=0.99)
    assert len(all_candidates) >= len(high_threshold)


def test_fact_candidate_spans_decode_to_exact_source_text() -> None:
    source = "  Alice will lead the project.  Bob owns the follow-up。"
    event = note_event(100, "notes", source)
    spans = extract_fact_candidate_spans(event)

    assert [source[start:end] for _text, _score, start, end in spans] == [
        text for text, _score, _start, _end in spans
    ]
    graph = encode_events_to_graph([event], tz_offset_hours=0)
    facts = [node for node in graph.all_nodes() if node.kind == "fact"]
    assert [decode_fact_candidate(event, node) for node in facts] == [node.body for node in facts]


def test_fact_decoder_rejects_wrong_source_event() -> None:
    first = note_event(100, "notes", "Alice will lead.")
    second = note_event(101, "notes", "Alice will lead.")
    graph = encode_events_to_graph([first], tz_offset_hours=0)
    fact = next(node for node in graph.all_nodes() if node.kind == "fact")

    assert decode_fact_candidate(second, fact) is None


def test_encode_events_to_graph_produces_episodes_and_facts() -> None:
    events = [
        note_event(1_700_000_000, "cli", "Alice will lead the project"),
        note_event(1_700_000_000 + 86400, "cli", "Bob submitted the report"),
    ]
    g = encode_events_to_graph(events, tz_offset_hours=0)
    assert g.node_count() > 0
    # At least two episodes (one per day)
    episodes = [n for n in g.all_nodes() if n.kind == "episode"]
    assert len(episodes) == 2
    # Facts should be derived from note content
    facts = [n for n in g.all_nodes() if n.kind == "fact"]
    assert len(facts) >= 2
    # Acyclic derived_from chain
    assert not g.has_cycle_along("derived_from")


def test_encode_deterministic() -> None:
    events = [
        note_event(100, "s", "Alice met Bob to discuss the plan"),
        message_event(200, "chat", "in", "alice", "let's do this"),
    ]
    g1 = encode_events_to_graph(events)
    g2 = encode_events_to_graph(events)
    assert g1.node_count() == g2.node_count()
    assert g1.edge_count() == g2.edge_count()
    ids_1 = {n.node_id for n in g1.all_nodes()}
    ids_2 = {n.node_id for n in g2.all_nodes()}
    assert ids_1 == ids_2


def test_dedupe_fact_candidates_removes_near_duplicates() -> None:
    from famulix.encoding import dedupe_fact_candidates

    candidates = [
        ("the project deadline is friday", 0.8, 0, 30),
        ("the project deadline is friday", 0.7, 40, 70),  # exact duplicate
        ("another unrelated fact here", 0.6, 80, 105),
    ]
    result = dedupe_fact_candidates(candidates)
    assert len(result) == 2
    assert result[0][0] == candidates[0][0]  # first occurrence kept


def test_dedupe_fact_candidates_keeps_distinct() -> None:
    from famulix.encoding import dedupe_fact_candidates

    candidates = [
        ("project deadline is friday", 0.8, 0, 25),
        ("weekly team meeting on monday", 0.7, 30, 60),
        ("buy groceries after work", 0.6, 70, 95),
    ]
    result = dedupe_fact_candidates(candidates)
    assert len(result) == 3


def test_dedupe_fact_candidates_empty_input() -> None:
    from famulix.encoding import dedupe_fact_candidates

    assert dedupe_fact_candidates([]) == []


def _span_node(event_id: str, start: int, end: int, label: str) -> MemoryNode:
    return MemoryNode.create(
        "fact",
        label,
        "value",
        created_at_s=5,
        metadata={
            "source_event": event_id,
            "source_start": str(start),
            "source_end": str(end),
        },
    )


def test_decode_fact_candidate_returns_none_for_non_text_payload() -> None:
    """A malformed event payload must not raise during span reconstruction."""
    event = note_event(100, "test", "weird note")
    event.data["text"] = {"not": "a string"}
    node = _span_node(event.event_id, 0, 4, "non text payload")
    assert decode_fact_candidate(event, node) is None


def test_decode_fact_candidate_rejects_out_of_range_spans() -> None:
    event = note_event(5, "test", "move the standup to Thursday")
    assert decode_fact_candidate(event, _span_node(event.event_id, 0, 4, "s1")) == "move"
    assert decode_fact_candidate(event, _span_node(event.event_id, 5, 8, "s2")) == "the"
    assert decode_fact_candidate(event, _span_node(event.event_id, -1, 4, "s3")) is None
    assert decode_fact_candidate(event, _span_node(event.event_id, 9, 3, "s4")) is None
    assert decode_fact_candidate(event, _span_node(event.event_id, 0, 10_000, "s5")) is None


def test_decode_fact_candidate_ignores_other_events_and_kinds() -> None:
    event = note_event(5, "test", "move the standup to Thursday")
    other = note_event(6, "test", "unrelated text")
    node = _span_node(event.event_id, 0, 4, "s6")
    assert decode_fact_candidate(other, node) is None
    episode = MemoryNode.create(
        "episode", "s7", "body", created_at_s=5, metadata={"source_event": event.event_id}
    )
    assert decode_fact_candidate(event, episode) is None


def test_extract_entities_handles_hostile_text() -> None:
    from famulix.encoding import extract_entities

    hostile = "Contact <script>alert('xss')</script> at alice@example.com"
    entities = extract_entities(hostile)
    assert isinstance(entities, list)


def test_extract_entities_handles_unicode_names() -> None:
    from famulix.encoding import extract_entities

    text = "Meeting with 张伟 and María García about the project"
    entities = extract_entities(text)
    assert isinstance(entities, list)


def test_extract_fact_candidates_handles_non_note_events() -> None:
    from famulix.encoding import extract_fact_candidates
    from famulix.events import Event

    event = Event(
        event_id="binary1",
        event_type="file_touch",
        timestamp_s=1000,
        source="test",
        data={"path": "/some/file.txt"},
    )
    candidates = extract_fact_candidates(event)
    assert isinstance(candidates, list)


def test_day_segment_handles_dst_boundary() -> None:
    from datetime import datetime, timedelta, timezone

    from famulix.encoding import day_segment
    from famulix.events import Event

    tz = timezone(timedelta(hours=8))
    base = datetime(2026, 3, 8, 2, 0, tzinfo=tz)
    events = [
        Event(
            event_id=f"e{i}",
            event_type="note",
            timestamp_s=int(base.timestamp()) + i * 3600,
            source="test",
            data={"text": f"event {i}"},
        )
        for i in range(24)
    ]
    segments = day_segment(events, tz_offset_hours=8)
    assert isinstance(segments, dict)
    assert len(segments) >= 1
