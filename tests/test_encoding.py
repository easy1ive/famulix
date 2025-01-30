"""Tests for the encoding pipeline."""

from __future__ import annotations

from famulix.encoding import (
    day_segment,
    encode_events_to_graph,
    extract_entities,
    extract_fact_candidates,
)
from famulix.events import message_event, note_event


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
