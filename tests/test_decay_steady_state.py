"""Tests for decay steady-state simulation."""

from famulix.decay import simulate_steady_state


def test_steady_state_all_tiers_populated():
    result = simulate_steady_state(total_memories=100, seed=42)
    assert sum(result.values()) == 100
    assert all(v >= 0 for v in result.values())


def test_steady_state_deterministic():
    a = simulate_steady_state(total_memories=500, seed=99)
    b = simulate_steady_state(total_memories=500, seed=99)
    assert a == b


def test_steady_state_different_seeds_same_total():
    a = simulate_steady_state(total_memories=500, seed=1)
    b = simulate_steady_state(total_memories=500, seed=2)
    assert sum(a.values()) == sum(b.values()) == 500


def test_steady_state_custom_thresholds():
    thresholds = {"active": 0.6, "stale": 0.0}
    result = simulate_steady_state(tier_thresholds=thresholds, total_memories=200, seed=7)
    assert sum(result.values()) == 200
    assert "active" in result
    assert "stale" in result


def test_steady_state_hot_tier_smaller_than_archive():
    """With uniform random salience, higher thresholds yield fewer memories."""
    thresholds = {"hot": 0.9, "warm": 0.5, "cold": 0.1, "archive": 0.0}
    result = simulate_steady_state(tier_thresholds=thresholds, total_memories=10000, seed=42)
    assert result["hot"] < result["archive"]
    assert result["hot"] < result["warm"]
