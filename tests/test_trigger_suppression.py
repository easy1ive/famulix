"""Tests for trigger suppression when briefing covers the item."""

from famulix.triggers import suppress_covered


def test_suppresses_covered_trigger():
    triggers = [
        {"id": "t1", "source_memory_id": "mem_a", "kind": "reminder"},
        {"id": "t2", "source_memory_id": "mem_b", "kind": "reminder"},
    ]
    covered = {"mem_a"}
    result = suppress_covered(triggers, covered)
    assert len(result) == 1
    assert result[0]["id"] == "t2"


def test_no_suppression_when_not_covered():
    triggers = [
        {"id": "t1", "source_memory_id": "mem_a", "kind": "reminder"},
    ]
    covered = {"mem_z"}
    result = suppress_covered(triggers, covered)
    assert len(result) == 1


def test_empty_triggers():
    result = suppress_covered([], {"mem_a"})
    assert result == []


def test_trigger_without_source_id_not_suppressed():
    triggers: list[dict[str, object]] = [{"id": "t1", "kind": "timer"}]
    result = suppress_covered(triggers, {"mem_a"})
    assert len(result) == 1


def test_all_covered():
    triggers = [
        {"id": "t1", "source_memory_id": "mem_a"},
        {"id": "t2", "source_memory_id": "mem_b"},
    ]
    covered = {"mem_a", "mem_b"}
    result = suppress_covered(triggers, covered)
    assert result == []
