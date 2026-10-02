"""Tests for trigger cooldown boundary and edge cases."""

from famulix.trigger_cooldown import CooldownTracker


def test_cooldown_exact_boundary():
    """Firing is allowed at exactly the cooldown boundary."""
    tracker = CooldownTracker(cooldown_seconds=100)
    tracker.record_fire("t1", current_time_s=1000)
    # At exactly 1100, cooldown has elapsed
    assert tracker.can_fire("t1", current_time_s=1100)


def test_cooldown_one_second_before():
    """Firing is blocked one second before the cooldown ends."""
    tracker = CooldownTracker(cooldown_seconds=100)
    tracker.record_fire("t1", current_time_s=1000)
    assert not tracker.can_fire("t1", current_time_s=1099)


def test_cooldown_zero_allows_immediate():
    """Zero-second cooldown allows immediate re-fire."""
    tracker = CooldownTracker(cooldown_seconds=0)
    tracker.record_fire("t1", current_time_s=1000)
    assert tracker.can_fire("t1", current_time_s=1000)


def test_cooldown_multiple_records():
    """Latest fire time is used for cooldown calculation."""
    tracker = CooldownTracker(cooldown_seconds=100)
    tracker.record_fire("t1", current_time_s=1000)
    tracker.record_fire("t1", current_time_s=1050)
    # Should be blocked until 1150 (1050 + 100)
    assert not tracker.can_fire("t1", current_time_s=1100)
    assert tracker.can_fire("t1", current_time_s=1150)


def test_cooldown_tracker_deterministic():
    t1 = CooldownTracker(cooldown_seconds=500)
    t2 = CooldownTracker(cooldown_seconds=500)
    t1.record_fire("x", current_time_s=100)
    t2.record_fire("x", current_time_s=100)
    assert t1.can_fire("x", current_time_s=600) == t2.can_fire("x", current_time_s=600)
