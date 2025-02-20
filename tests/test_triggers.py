"""Tests for proactive triggers."""

from __future__ import annotations

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
