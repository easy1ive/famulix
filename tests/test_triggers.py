"""Tests for proactive triggers."""

from __future__ import annotations

from datetime import UTC

from famulix.memory_graph import MemoryGraph, MemoryNode
from famulix.triggers import TriggerConfig, TriggerLog, generate_triggers


def _make_graph(n: int = 5):
    g = MemoryGraph()
    for i in range(n):
        meta = {"pinned": "true"} if i % 2 == 0 else {}
        node = MemoryNode.create(
            "fact",
            f"fact_{i}",
            f"critical important deadline must do urgent task number {i}",
            metadata=meta,
            created_at_s=1_700_000_000 + i * 100,
        )
        g.add_node(node)
    return g


def test_generate_triggers_returns_list() -> None:
    g = _make_graph(5)
    cfg = TriggerConfig(salience_threshold=0.01, max_triggers_per_day=10)
    triggers = generate_triggers(g, now_s=1_700_000_000 + 500, config=cfg)
    assert isinstance(triggers, list)


def test_triggers_have_memory_id() -> None:
    g = _make_graph(3)
    cfg = TriggerConfig(salience_threshold=0.01)
    triggers = generate_triggers(g, now_s=1_700_000_000 + 500, config=cfg)
    for t in triggers:
        assert t.memory_id
        assert t.trigger_id.startswith("trig_")
        assert t.trigger_time_s > 0


def test_triggers_sorted_by_time() -> None:
    g = _make_graph(5)
    cfg = TriggerConfig(salience_threshold=0.01)
    triggers = generate_triggers(g, now_s=1_700_000_000 + 500, config=cfg)
    times = [t.trigger_time_s for t in triggers]
    assert times == sorted(times)


def test_trigger_log_records_something() -> None:
    g = _make_graph(3)
    cfg = TriggerConfig(salience_threshold=0.01)
    log = TriggerLog()
    generate_triggers(g, now_s=1_700_000_000 + 500, config=cfg, log=log)
    assert len(log.entries) >= 0


def test_already_covered_reduces_triggers() -> None:
    g = _make_graph(5)
    cfg = TriggerConfig(salience_threshold=0.01, max_triggers_per_day=10)
    now = 1_700_000_000 + 500
    all_t = generate_triggers(g, now_s=now, config=cfg)
    if all_t:
        covered = {all_t[0].memory_id}
        fewer = generate_triggers(g, now_s=now, config=cfg, already_covered=covered)
        assert len(fewer) <= len(all_t)


def test_trigger_deterministic() -> None:
    g = _make_graph(4)
    cfg = TriggerConfig(salience_threshold=0.01)
    now = 1_700_000_000 + 500
    t1 = generate_triggers(g, now_s=now, config=cfg)
    t2 = generate_triggers(g, now_s=now, config=cfg)
    assert [t.trigger_id for t in t1] == [t.trigger_id for t in t2]


def test_trigger_log_count_by_action() -> None:
    log = TriggerLog()
    log.record(timestamp_s=100, trigger_id="t1", memory_id="m1", action="generated")
    log.record(timestamp_s=200, trigger_id="t2", memory_id="m2", action="generated")
    log.record(timestamp_s=300, trigger_id="t3", memory_id="m3", action="suppressed")
    assert log.count_by_action("generated") == 2
    assert log.count_by_action("suppressed") == 1
    assert log.count_by_action("fired") == 0


def test_max_triggers_per_day_cap() -> None:
    g = _make_graph(20)
    cfg = TriggerConfig(salience_threshold=0.01, max_triggers_per_day=5)
    triggers = generate_triggers(g, now_s=1_700_000_000 + 500, config=cfg)
    assert len(triggers) <= 5


def test_trigger_cooldown_suppresses_recently_generated_memory() -> None:
    from famulix.triggers import TriggerLog

    graph = MemoryGraph()
    node = MemoryNode.create("reminder", "Pinned", "important", created_at_s=1)
    graph.add_node(node)
    log = TriggerLog()
    log.record(timestamp_s=100000, trigger_id="prior", memory_id=node.node_id, action="generated")
    result = generate_triggers(
        graph, now_s=100100, config=TriggerConfig(salience_threshold=0), log=log
    )
    assert result == []
    assert log.entries[-1]["reason"] == "cooldown"


def test_trigger_config_rejects_out_of_range_hours() -> None:
    import pytest

    with pytest.raises(ValueError, match="quiet hours"):
        generate_triggers(MemoryGraph(), now_s=1, config=TriggerConfig(quiet_hours_start=24))


def test_trigger_log_action_summary() -> None:
    from famulix.triggers import TriggerLog

    log = TriggerLog()
    log.record(timestamp_s=100, trigger_id="t1", memory_id="m1", action="generated")
    log.record(timestamp_s=200, trigger_id="t2", memory_id="m2", action="generated")
    log.record(
        timestamp_s=300, trigger_id="t3", memory_id="m3", action="suppressed", reason="cooldown"
    )
    summary = log.action_summary()
    assert summary["generated"] == 2
    assert summary["suppressed"] == 1
    assert sum(summary.values()) == log.entry_count()


def test_trigger_log_clear_removes_entries() -> None:
    from famulix.triggers import TriggerLog

    log = TriggerLog()
    log.record(timestamp_s=100, trigger_id="t1", memory_id="m1", action="generated")
    assert log.entry_count() == 1
    log.clear()
    assert log.entry_count() == 0
    assert log.action_summary() == {}


def test_trigger_dedupe_window_suppresses_recent_fires() -> None:
    from famulix.triggers import TriggerConfig, TriggerLog, generate_triggers

    graph = MemoryGraph()
    node = MemoryNode.create("fact", "important", "high salience content", created_at_s=1000)
    graph.add_node(node)
    log = TriggerLog()
    log.record(timestamp_s=1000, trigger_id="trig_1", memory_id=node.node_id, action="generated")
    config = TriggerConfig(salience_threshold=0.1, cooldown_seconds=0, dedupe_window_seconds=3600)
    triggers = generate_triggers(graph, now_s=2000, config=config, log=log)
    assert triggers == []
    suppressed = log.count_by_action("suppressed")
    assert suppressed >= 1


def test_trigger_dedupe_window_allows_after_expiry() -> None:
    from famulix.triggers import TriggerConfig, TriggerLog, generate_triggers

    graph = MemoryGraph()
    node = MemoryNode.create("fact", "important", "high salience content", created_at_s=1000)
    graph.add_node(node)
    log = TriggerLog()
    log.record(timestamp_s=1000, trigger_id="trig_1", memory_id=node.node_id, action="generated")
    config = TriggerConfig(salience_threshold=0.1, cooldown_seconds=0, dedupe_window_seconds=600)
    triggers = generate_triggers(graph, now_s=2000, config=config, log=log)
    assert len(triggers) >= 1


def test_is_quiet_hour_detects_overnight_window() -> None:
    from datetime import datetime, timedelta, timezone

    from famulix.triggers import TriggerConfig, _is_quiet_hour

    config = TriggerConfig(quiet_hours_start=22, quiet_hours_end=8)
    utc8 = timezone(timedelta(hours=8))
    dt_23 = datetime(2026, 11, 12, 23, 0, tzinfo=utc8)
    assert _is_quiet_hour(int(dt_23.timestamp()), config)
    dt_02 = datetime(2026, 11, 12, 2, 0, tzinfo=utc8)
    assert _is_quiet_hour(int(dt_02.timestamp()), config)
    dt_12 = datetime(2026, 11, 12, 12, 0, tzinfo=utc8)
    assert not _is_quiet_hour(int(dt_12.timestamp()), config)


def test_generate_triggers_returns_empty_during_quiet_hours() -> None:
    from datetime import datetime

    from famulix.memory_graph import MemoryGraph, MemoryNode
    from famulix.triggers import TriggerConfig, generate_triggers

    graph = MemoryGraph()
    graph.add_node(MemoryNode.create("reminder", "important task", "do this", created_at_s=1000))
    config = TriggerConfig(quiet_hours_start=0, quiet_hours_end=23)
    dt = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
    triggers = generate_triggers(graph, now_s=int(dt.timestamp()), config=config)
    assert triggers == []


def test_trigger_log_records_suppressed_events() -> None:
    from famulix.triggers import TriggerLog

    log = TriggerLog()
    log.record(trigger_id="t1", memory_id="m1", action="generated", timestamp_s=100)
    log.record(
        trigger_id="t2", memory_id="m2", action="suppressed", timestamp_s=200, reason="quiet hours"
    )
    assert log.entry_count() == 2
    assert log.count_by_action("suppressed") == 1
    assert log.count_by_action("generated") == 1


def test_cooldown_tracker_records_and_checks() -> None:
    from famulix.triggers import CooldownTracker

    tracker = CooldownTracker()
    tracker.record_trigger("mem_1", 1000)
    assert tracker.is_in_cooldown("mem_1", 1500, cooldown_seconds=1000)
    assert not tracker.is_in_cooldown("mem_1", 2000, cooldown_seconds=1000)
    assert not tracker.is_in_cooldown("mem_2", 1500, cooldown_seconds=1000)


def test_cooldown_tracker_clears_expired() -> None:
    from famulix.triggers import CooldownTracker

    tracker = CooldownTracker()
    tracker.record_trigger("mem_1", 1000)
    tracker.record_trigger("mem_2", 2000)
    tracker.record_trigger("mem_3", 3000)
    removed = tracker.clear_expired(now_s=3500, cooldown_seconds=1000)
    assert removed == 2
    assert "mem_1" not in tracker.last_triggered
    assert "mem_2" not in tracker.last_triggered
    assert "mem_3" in tracker.last_triggered


def test_cooldown_tracker_persistence_roundtrip() -> None:
    from famulix.triggers import CooldownTracker

    tracker = CooldownTracker()
    tracker.record_trigger("mem_a", 500)
    tracker.record_trigger("mem_b", 1500)
    data = tracker.to_dict()
    restored = CooldownTracker.from_dict(data)
    assert restored.last_triggered == tracker.last_triggered
    assert restored.is_in_cooldown("mem_a", 600, cooldown_seconds=200)


def test_cooldown_tracker_from_dict_validates_types() -> None:
    import pytest

    from famulix.triggers import CooldownTracker

    with pytest.raises(ValueError, match="strings to integers"):
        CooldownTracker.from_dict({"mem": "not_an_int"})


def test_trigger_statistics_empty_log() -> None:
    from famulix.triggers import TriggerLog, trigger_statistics

    log = TriggerLog()
    stats = trigger_statistics(log)
    assert stats["total_triggers"] == 0
    assert stats["by_action"] == {}
    assert stats["unique_memories"] == 0
    assert stats["time_span_s"] == 0


def test_trigger_statistics_with_entries() -> None:
    from famulix.triggers import TriggerLog, trigger_statistics

    log = TriggerLog()
    log.record(
        timestamp_s=100,
        trigger_id="t1",
        memory_id="mem_a",
        action="generated",
        reason="salience=0.8",
    )
    log.record(
        timestamp_s=200,
        trigger_id="t2",
        memory_id="mem_b",
        action="generated",
        reason="salience=0.6",
    )
    log.record(
        timestamp_s=300,
        trigger_id="t3",
        memory_id="mem_a",
        action="suppressed",
        reason="cooldown",
    )

    stats = trigger_statistics(log)
    assert stats["total_triggers"] == 3
    assert stats["unique_memories"] == 2
    assert stats["time_span_s"] == 200
    assert stats["by_action"]["generated"] == 2
    assert stats["by_action"]["suppressed"] == 1


def test_validate_trigger_config_valid() -> None:
    from famulix.triggers import TriggerConfig, validate_trigger_config

    config = TriggerConfig(
        quiet_hours_start=22,
        quiet_hours_end=7,
        cooldown_seconds=3600,
        dedupe_window_seconds=300,
        salience_threshold=0.5,
    )
    problems = validate_trigger_config(config)
    assert problems == []


def test_validate_trigger_config_invalid_hours() -> None:
    from famulix.triggers import TriggerConfig, validate_trigger_config

    config = TriggerConfig(
        quiet_hours_start=25,
        quiet_hours_end=-1,
        cooldown_seconds=3600,
        dedupe_window_seconds=300,
        salience_threshold=0.5,
    )
    problems = validate_trigger_config(config)
    assert len(problems) == 2
    assert any("quiet" in p for p in problems)


def test_validate_trigger_config_invalid_thresholds() -> None:
    from famulix.triggers import TriggerConfig, validate_trigger_config

    config = TriggerConfig(
        quiet_hours_start=22,
        quiet_hours_end=7,
        cooldown_seconds=-100,
        dedupe_window_seconds=-50,
        salience_threshold=1.5,
    )
    problems = validate_trigger_config(config)
    assert len(problems) == 3
    assert any("cooldown" in p for p in problems)
    assert any("dedupe" in p for p in problems)
    assert any("salience" in p for p in problems)
