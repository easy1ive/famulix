"""Tests for the daily briefing application."""

from __future__ import annotations

from datetime import UTC

from famulix.briefing import (
    BriefingItem,
    build_briefing,
    build_briefing_from_connectors,
    gather_memories,
    render_briefing_html,
    render_briefing_markdown,
)
from famulix.connectors import ConnectorHub, ConnectorRecord, ScriptedConnector
from famulix.memory_graph import MemoryGraph, MemoryNode


def _populate_graph() -> MemoryGraph:
    g = MemoryGraph()
    facts = [
        ("project deadline is friday", "Must submit report by end of week", 1000),
        ("dentist appointment", "Monday 2pm cleaning", 500),
        ("buy groceries", "milk, eggs, bread", 200),
        ("team meeting", "weekly sync at 10am", 800),
        ("gym reminder", "tuesday and thursday 6pm", 300),
    ]
    for i, (title, body, ts) in enumerate(facts):
        kind = "reminder" if "reminder" in title or "appointment" in title else "fact"
        if "deadline" in title:
            kind = "goal"
        node = MemoryNode.create(
            kind=kind,
            title=title,
            body=body,
            created_at_s=ts,
            metadata={"importance": str(i * 0.2)},
        )
        g.add_node(node)
    return g


def test_gather_memories_returns_items():
    g = _populate_graph()
    items = gather_memories(g, now_s=1200, budget_tokens=200)
    assert len(items) > 0
    for item in items:
        assert isinstance(item, BriefingItem)
        assert item.memory_ids
        assert len(item.memory_ids) >= 1


def test_gather_memories_respects_budget():
    g = _populate_graph()
    items = gather_memories(g, now_s=1200, budget_tokens=50)
    total_tokens = sum(len(it.body.split()) for it in items)
    assert total_tokens <= 50 * 2  # rough bound since estimate_tokens is len-based


def test_build_briefing_structure():
    g = _populate_graph()
    briefing = build_briefing(
        g,
        date_str="2026-01-15",
        now_s=1200,
        budget_tokens=300,
        version="0.1.0",
        seed=42,
        config_hash="abc123",
    )
    assert briefing.date_str == "2026-01-15"
    assert "2026-01-15" in briefing.title
    assert len(briefing.items) > 0
    assert len(briefing.sections) > 0
    assert briefing.metadata["version"] == "0.1.0"
    assert briefing.metadata["seed"] == "42"
    assert len(briefing.limitations) >= 3


def test_citations_resolve_against_graph():
    g = _populate_graph()
    briefing = build_briefing(g, date_str="2026-01-15", now_s=1200)
    assert briefing.citations_resolve(g)


def test_citations_do_not_resolve_when_node_deleted():
    g = _populate_graph()
    briefing = build_briefing(g, date_str="2026-01-15", now_s=1200)
    first_id = next(iter(briefing.all_cited_memory_ids()))
    node = g.get_node(first_id)
    assert node is not None
    from dataclasses import replace

    g._nodes[first_id] = replace(node, is_active=False)
    assert not briefing.citations_resolve(g)


def test_sections_are_ordered():
    g = _populate_graph()
    briefing = build_briefing(g, date_str="2026-01-15", now_s=1200)
    section_order = {"agenda": 0, "commitments": 1, "reminders": 2, "recent_memories": 3}
    prev_rank = -1
    for s in briefing.sections:
        rank = section_order.get(s, 99)
        assert rank >= prev_rank
        prev_rank = rank


def test_render_markdown_contains_sections():
    g = _populate_graph()
    briefing = build_briefing(g, date_str="2026-01-15", now_s=1200)
    md = render_briefing_markdown(briefing)
    assert "# Daily Briefing" in md
    assert "limitations" in md.lower()
    # section names are present as Markdown headings (underscores may be escaped)
    assert "## commitments" in md
    assert "## reminders" in md
    assert "limitations" in md.lower()


def test_render_html_is_self_contained():
    g = _populate_graph()
    briefing = build_briefing(g, date_str="2026-01-15", now_s=1200)
    html = render_briefing_html(briefing, graph=g)
    assert html.startswith("<!DOCTYPE html>")
    assert "<html" in html
    assert "<style>" in html
    assert "</body></html>" in html
    assert "<svg" in html  # charts included


def test_render_html_escapes_hostile_text():
    g = MemoryGraph()
    node = MemoryNode.create(
        kind="fact",
        title="<script>alert('xss')</script>",
        body="<img src=x onerror=alert(1)>",
        created_at_s=100,
    )
    g.add_node(node)
    briefing = build_briefing(g, date_str="2026-01-15", now_s=200)
    html = render_briefing_html(briefing, graph=g)
    # actual HTML tags are escaped, so no raw <script> or <img> tags
    assert "<script>" not in html
    assert "<img" not in html
    # escaped versions are present
    assert "&lt;script&gt;" in html or "&lt;script" in html
    assert "&lt;img" in html


def test_briefing_determinism_same_seed():
    g = _populate_graph()
    b1 = build_briefing(g, date_str="2026-01-15", now_s=1200, seed=42)
    b2 = build_briefing(g, date_str="2026-01-15", now_s=1200, seed=42)
    assert [it.title for it in b1.items] == [it.title for it in b2.items]
    assert b1.metadata == b2.metadata


def test_empty_graph_produces_briefing_with_limitations():
    g = MemoryGraph()
    briefing = build_briefing(g, date_str="2026-01-15", now_s=1200)
    assert len(briefing.items) == 0
    assert len(briefing.limitations) >= 3
    md = render_briefing_markdown(briefing)
    assert "limitations" in md.lower()


def test_all_cited_memory_ids_unique_set():
    g = _populate_graph()
    briefing = build_briefing(g, date_str="2026-01-15", now_s=1200)
    all_ids = briefing.all_cited_memory_ids()
    assert isinstance(all_ids, set)
    # each item has one id, unique set should equal number of items
    assert len(all_ids) == len(briefing.items)


def test_connector_pipeline_builds_deterministic_resolvable_briefing() -> None:
    connector = ScriptedConnector(
        "notes",
        (
            ConnectorRecord(
                "notes", "n1", "note", 1_700_000_000, "plan", "Review the project plan"
            ),
            ConnectorRecord("notes", "n2", "note", 1_700_000_100, "meeting", "Team sync at 10"),
        ),
    )
    hub = ConnectorHub([connector])
    graph, first = build_briefing_from_connectors(
        hub, date_str="2026-11-12", now_s=1_700_001_000, seed=9
    )
    second_graph, second = build_briefing_from_connectors(
        hub, date_str="2026-11-12", now_s=1_700_001_000, seed=9
    )

    assert first.citations_resolve(graph)
    assert first.all_cited_memory_ids() == second.all_cited_memory_ids()
    assert [item.title for item in first.items] == [item.title for item in second.items]
    assert all(graph.get_node(memory_id) for memory_id in second.all_cited_memory_ids())
    assert graph.node_count() == second_graph.node_count()


def test_briefing_visuals_reflect_graph_activity_dates() -> None:
    from datetime import datetime

    from famulix.briefing import build_briefing, render_briefing_html
    from famulix.memory_graph import MemoryGraph, MemoryNode

    graph = MemoryGraph()
    node = MemoryNode.create(
        "fact",
        "Focus",
        "ship the draft",
        created_at_s=int(datetime(2026, 11, 12, 9, tzinfo=UTC).timestamp()),
    )
    graph.add_node(node)
    briefing = build_briefing(graph, date_str="2026-11-12", now_s=node.created_at_s, seed=0)
    markup = render_briefing_html(briefing, graph=graph)
    assert "Memory salience by local day and hour" in markup
    assert "7-day retention heatmap" not in markup


def test_empty_briefing_omits_unrepresented_day_heatmap() -> None:
    from famulix.briefing import build_briefing, render_briefing_html
    from famulix.memory_graph import MemoryGraph

    graph = MemoryGraph()
    briefing = build_briefing(graph, date_str="2026-11-12", now_s=0)
    markup = render_briefing_html(briefing, graph=graph)
    assert "Memory salience by local day and hour" not in markup
    assert "<svg" in markup


def test_agenda_section_includes_day_bound_reminders() -> None:
    from famulix.briefing import build_agenda_section
    from famulix.memory_graph import MemoryGraph, MemoryNode

    g = MemoryGraph()
    day_start = 86400 * 10
    day_end = day_start + 86400
    g.add_node(
        MemoryNode(
            node_id="r1",
            kind="reminder",
            title="dentist",
            body="appt",
            created_at_s=day_start + 3600,
            is_active=True,
            metadata={"due_at_s": str(day_start + 3600 * 10)},
        )
    )
    g.add_node(
        MemoryNode(
            node_id="r2",
            kind="reminder",
            title="far",
            body="later",
            created_at_s=day_start + 100,
            is_active=True,
            metadata={"due_at_s": str(day_end + 1000)},
        )
    )
    items = build_agenda_section(g, day_start_s=day_start, day_end_s=day_end)
    assert any("dentist" in it.title for it in items)
    assert not any("far" in it.title for it in items)


def test_agenda_section_includes_calendar_episodes() -> None:
    from famulix.briefing import build_agenda_section
    from famulix.memory_graph import MemoryGraph, MemoryNode

    g = MemoryGraph()
    day_start = 86400 * 5
    day_end = day_start + 86400
    g.add_node(
        MemoryNode(
            node_id="e1",
            kind="episode",
            title="team sync",
            body="weekly",
            created_at_s=day_start + 7200,
            is_active=True,
            metadata={"event_types": "calendar,note"},
        )
    )
    items = build_agenda_section(g, day_start_s=day_start, day_end_s=day_end)
    assert any(it.section == "agenda" and "team sync" in it.title for it in items)


def test_commitments_section_prioritizes_overdue_goals() -> None:
    from famulix.briefing import build_commitments_section
    from famulix.memory_graph import MemoryGraph, MemoryNode

    g = MemoryGraph()
    now = 100000
    g.add_node(
        MemoryNode(
            node_id="g1",
            kind="goal",
            title="overdue",
            body="past due",
            created_at_s=100,
            is_active=True,
            metadata={"due_at_s": str(now - 1000)},
        )
    )
    g.add_node(
        MemoryNode(
            node_id="g2",
            kind="goal",
            title="soon",
            body="next week",
            created_at_s=200,
            is_active=True,
            metadata={"due_at_s": str(now + 86400 * 5)},
        )
    )
    g.add_node(
        MemoryNode(
            node_id="g3",
            kind="goal",
            title="far",
            body="far future",
            created_at_s=300,
            is_active=True,
            metadata={"due_at_s": str(now + 86400 * 60)},
        )
    )
    items = build_commitments_section(g, now_s=now, horizon_s=86400 * 14)
    titles = [it.title for it in items]
    assert "overdue" in titles
    assert "soon" in titles
    assert "far" not in titles
    assert items[0].title == "overdue"


def test_build_briefing_dedupes_memory_ids_across_sections() -> None:
    from famulix.briefing import build_briefing
    from famulix.memory_graph import MemoryGraph, MemoryNode

    g = MemoryGraph()
    now = 86400 * 20 + 3600 * 10
    g.add_node(
        MemoryNode(
            node_id="goal1",
            kind="goal",
            title="finish report",
            body="complete Q4 report",
            created_at_s=now - 86400 * 2,
            is_active=True,
            metadata={"due_at_s": str(now + 86400 * 3)},
        )
    )
    briefing = build_briefing(g, date_str="2026-01-20", now_s=now, seed=0)
    ids = briefing.all_cited_memory_ids()
    # Each id appears at most once across all items
    assert len(ids) == len(briefing.items)


def test_reminders_section_filters_by_lookahead() -> None:
    from famulix.briefing import build_reminders_section
    from famulix.memory_graph import MemoryGraph, MemoryNode

    g = MemoryGraph()
    now = 100000
    g.add_node(
        MemoryNode(
            node_id="r1",
            kind="reminder",
            title="pay rent",
            body="due soon",
            created_at_s=100,
            is_active=True,
            metadata={"due_at_s": str(now + 86400)},
        )
    )
    g.add_node(
        MemoryNode(
            node_id="r2",
            kind="reminder",
            title="annual review",
            body="far future",
            created_at_s=200,
            is_active=True,
            metadata={"due_at_s": str(now + 86400 * 30)},
        )
    )
    g.add_node(
        MemoryNode(
            node_id="r3",
            kind="reminder",
            title="overdue bill",
            body="past due",
            created_at_s=50,
            is_active=True,
            metadata={"due_at_s": str(now - 5000)},
        )
    )
    items = build_reminders_section(g, now_s=now, lookahead_s=86400 * 3)
    titles = [it.title for it in items]
    assert "pay rent" in titles
    assert "overdue bill" in titles
    assert "annual review" not in titles
    assert items[0].title == "overdue bill"  # overdue has highest priority


def test_reminders_section_skips_inactive_nodes() -> None:
    from famulix.briefing import build_reminders_section
    from famulix.memory_graph import MemoryGraph, MemoryNode

    g = MemoryGraph()
    now = 100000
    g.add_node(
        MemoryNode(
            node_id="r1",
            kind="reminder",
            title="inactive",
            body="should not appear",
            created_at_s=100,
            is_active=False,
            metadata={"due_at_s": str(now + 1000)},
        )
    )
    items = build_reminders_section(g, now_s=now)
    assert len(items) == 0


def test_build_briefing_has_agenda_and_commitments_sections() -> None:
    from famulix.briefing import build_briefing
    from famulix.memory_graph import MemoryGraph, MemoryNode

    g = MemoryGraph()
    now = 86400 * 20 + 3600 * 10
    g.add_node(
        MemoryNode(
            node_id="c1",
            kind="episode",
            title="meeting",
            body="standup",
            created_at_s=now - 100,
            is_active=True,
            metadata={"event_types": "calendar"},
        )
    )
    g.add_node(
        MemoryNode(
            node_id="g1",
            kind="goal",
            title="report",
            body="finish report",
            created_at_s=now - 10000,
            is_active=True,
            metadata={"due_at_s": str(now + 86400 * 3)},
        )
    )
    briefing = build_briefing(g, date_str="2026-01-20", now_s=now, seed=0)
    assert "agenda" in briefing.sections
    assert "commitments" in briefing.sections
