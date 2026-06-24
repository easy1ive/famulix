"""Test trigger cooldown tracking."""

from famulix.trigger_cooldown import CooldownTracker


def test_cooldown_allows_first_fire():
    tracker = CooldownTracker(cooldown_seconds=3600)
    assert tracker.can_fire("t1", current_time_s=1000)


def test_cooldown_blocks_rapid_fire():
    tracker = CooldownTracker(cooldown_seconds=3600)
    tracker.record_fire("t1", current_time_s=1000)

    assert not tracker.can_fire("t1", current_time_s=1500)
    assert tracker.can_fire("t1", current_time_s=4600)


def test_cooldown_time_until_ready():
    tracker = CooldownTracker(cooldown_seconds=3600)
    tracker.record_fire("t1", current_time_s=1000)

    assert tracker.time_until_ready("t1", current_time_s=1000) == 3600
    assert tracker.time_until_ready("t1", current_time_s=2000) == 2600
    assert tracker.time_until_ready("t1", current_time_s=5000) == 0


def test_cooldown_independent_triggers():
    tracker = CooldownTracker(cooldown_seconds=3600)
    tracker.record_fire("t1", current_time_s=1000)

    assert not tracker.can_fire("t1", current_time_s=1500)
    assert tracker.can_fire("t2", current_time_s=1500)
