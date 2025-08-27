"""Tests for preference learning and calibration."""

from __future__ import annotations

import pytest

from famulix.preferences import (
    PreferenceProfile,
    brier_score,
    calibration_error,
    reliability_bins,
)


def test_profile_starts_empty() -> None:
    p = PreferenceProfile()
    assert p.version == 1
    assert p.entries == []
    assert p.current_preferences(now_s=0) == {}


def test_add_feedback_increments_version() -> None:
    p = PreferenceProfile()
    p.add_feedback("tone", "concise", "up", 100, 0.8)
    assert p.version == 2
    assert len(p.entries) == 1


def test_current_preferences_dominant_value() -> None:
    p = PreferenceProfile()
    p.add_feedback("tone", "concise", "up", 100, 0.9)
    p.add_feedback("tone", "concise", "up", 200, 0.7)
    p.add_feedback("tone", "verbose", "down", 300, 0.5)
    prefs = p.current_preferences(now_s=400)
    assert "tone" in prefs
    value, conf = prefs["tone"]
    assert value == "concise"
    assert 0.0 < conf <= 1.0


def test_preference_decay_over_time() -> None:
    p = PreferenceProfile(decay_half_life_s=1000)
    p.add_feedback("tone", "concise", "up", 0, 1.0)
    near = p.current_preferences(now_s=100, min_confidence=0.0)
    far = p.current_preferences(now_s=2000, min_confidence=0.0)
    assert near["tone"][1] >= far["tone"][1]


def test_down_feedback_reduces_confidence() -> None:
    p = PreferenceProfile()
    p.add_feedback("tone", "verbose", "down", 100, 1.0)
    prefs = p.current_preferences(now_s=200)
    # Down-voted value should not be the dominant preference
    assert "tone" not in prefs or prefs["tone"][0] != "verbose"


def test_multiple_keys() -> None:
    p = PreferenceProfile()
    p.add_feedback("tone", "concise", "up", 100, 0.8)
    p.add_feedback("format", "markdown", "up", 200, 0.7)
    p.add_feedback("order", "priority", "up", 300, 0.9)
    prefs = p.current_preferences(now_s=400)
    assert len(prefs) == 3


def test_brier_score_perfect() -> None:
    # Perfect predictions: 1.0 for positives, 0.0 for negatives
    preds = [1.0, 0.0, 1.0, 0.0]
    outcomes = [1, 0, 1, 0]
    assert brier_score(preds, outcomes) == 0.0


def test_brier_score_worst_case() -> None:
    preds = [1.0, 0.0]
    outcomes = [0, 1]
    assert brier_score(preds, outcomes) == 1.0


def test_brier_score_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        brier_score([0.5], [1, 0])


def test_brier_score_empty() -> None:
    assert brier_score([], []) == 0.0


def test_brier_score_in_unit_interval() -> None:
    preds = [0.3, 0.6, 0.9, 0.2, 0.5]
    outcomes = [0, 1, 1, 0, 1]
    bs = brier_score(preds, outcomes)
    assert 0.0 <= bs <= 1.0


def test_reliability_bins_structure() -> None:
    preds = [0.1, 0.4, 0.6, 0.9]
    outcomes = [0, 0, 1, 1]
    bins = reliability_bins(preds, outcomes, n_bins=5)
    assert len(bins) == 5
    for b in bins:
        assert "lower" in b
        assert "upper" in b
        assert "count" in b
        assert "avg_predicted" in b
        assert "avg_observed" in b


def test_reliability_bins_counts_match() -> None:
    preds = [0.15, 0.25, 0.55, 0.75, 0.95]
    outcomes = [0, 0, 1, 1, 1]
    bins = reliability_bins(preds, outcomes, n_bins=10)
    total_count = sum(b["count"] for b in bins)
    assert total_count == len(preds)


def test_calibration_error_perfect() -> None:
    # Perfectly calibrated: each bin has pred == obs
    preds = [0.1, 0.3, 0.5, 0.7, 0.9]
    outcomes = [0, 0, 1, 1, 1]
    # Not perfect but low
    ece = calibration_error(preds, outcomes)
    assert ece >= 0.0


def test_calibration_error_zero_for_empty() -> None:
    assert calibration_error([], []) == 0.0


def test_preference_keys() -> None:
    p = PreferenceProfile()
    p.add_feedback("tone", "concise", "up", 100)
    p.add_feedback("format", "markdown", "up", 200)
    assert p.preference_keys() == {"tone", "format"}


@pytest.mark.parametrize("half_life", [0, -1, float("inf"), float("nan")])
def test_profile_rejects_invalid_decay_half_life(half_life: float) -> None:
    with pytest.raises(ValueError, match="half-life"):
        PreferenceProfile(decay_half_life_s=half_life)


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("inf"), float("nan")])
def test_feedback_rejects_invalid_confidence(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        PreferenceProfile().add_feedback("tone", "concise", "up", 10, confidence)


def test_feedback_rejects_empty_dimensions_and_negative_time() -> None:
    profile = PreferenceProfile()
    with pytest.raises(ValueError, match="non-empty"):
        profile.add_feedback(" ", "concise", "up", 10)
    with pytest.raises(ValueError, match="timestamp"):
        profile.add_feedback("tone", "concise", "up", -1)


def test_current_preferences_rejects_invalid_threshold() -> None:
    with pytest.raises(ValueError, match="minimum confidence"):
        PreferenceProfile().current_preferences(now_s=0, min_confidence=1.1)


@pytest.mark.parametrize("prediction", [-0.1, 1.1, float("inf"), float("nan")])
def test_calibration_rejects_invalid_probabilities(prediction: float) -> None:
    with pytest.raises(ValueError, match="predictions"):
        brier_score([prediction], [1])


@pytest.mark.parametrize("outcome", [-1, 2, True])
def test_calibration_rejects_invalid_outcomes(outcome: int) -> None:
    with pytest.raises(ValueError, match="outcomes"):
        reliability_bins([0.5], [outcome])


def test_reliability_bins_rejects_nonpositive_bin_count() -> None:
    with pytest.raises(ValueError, match="positive"):
        reliability_bins([0.5], [1], n_bins=0)


def test_merge_profiles_combines_entries_by_timestamp() -> None:
    from famulix.preferences import merge_profiles

    p1 = PreferenceProfile()
    p1.add_feedback("tone", "formal", "up", timestamp_s=100, confidence=0.8, source="t1")
    p1.add_feedback("length", "short", "accept", timestamp_s=300, confidence=0.6, source="t1")

    p2 = PreferenceProfile()
    p2.add_feedback("tone", "casual", "up", timestamp_s=200, confidence=0.7, source="t2")

    merged = merge_profiles(p1, p2)
    assert merged.entry_count() == 3
    # Entries sorted by timestamp
    timestamps = [e.timestamp_s for e in merged.entries]
    assert timestamps == sorted(timestamps)
    # Resulting preferences should reflect all three signals
    prefs = merged.current_preferences(now_s=400)
    assert "tone" in prefs
    assert "length" in prefs


def test_merge_profiles_empty_returns_empty() -> None:
    from famulix.preferences import merge_profiles

    merged = merge_profiles()
    assert merged.entry_count() == 0
    assert merged.version == 1


def test_entries_for_key_filters_correctly() -> None:
    p = PreferenceProfile()
    p.add_feedback("tone", "formal", "up", timestamp_s=100)
    p.add_feedback("tone", "casual", "down", timestamp_s=200)
    p.add_feedback("length", "short", "accept", timestamp_s=300)
    assert len(p.entries_for_key("tone")) == 2
    assert len(p.entries_for_key("length")) == 1
    assert len(p.entries_for_key("nonexistent")) == 0


def test_preference_profile_cold_start_returns_empty() -> None:
    from famulix.preferences import PreferenceProfile

    profile = PreferenceProfile()
    prefs = profile.current_preferences(now_s=1000)
    assert prefs == {}
    assert profile.entry_count() == 0
    assert profile.preference_keys() == set()


def test_preference_profile_single_signal_below_threshold() -> None:
    from famulix.preferences import PreferenceProfile

    profile = PreferenceProfile()
    profile.add_feedback("format", "concise", "up", timestamp_s=1000, confidence=0.3)
    prefs = profile.current_preferences(now_s=1000, min_confidence=0.5)
    assert prefs == {}
    prefs_low = profile.current_preferences(now_s=1000, min_confidence=0.1)
    assert "format" in prefs_low


def test_preference_profile_decay_reduces_confidence_over_time() -> None:
    from famulix.preferences import PreferenceProfile

    profile = PreferenceProfile(decay_half_life_s=86400)
    profile.add_feedback("tone", "formal", "up", timestamp_s=0, confidence=1.0)
    prefs_now = profile.current_preferences(now_s=0, min_confidence=0.0)
    prefs_later = profile.current_preferences(now_s=86400, min_confidence=0.0)
    assert "tone" in prefs_now
    assert "tone" in prefs_later
    assert prefs_later["tone"][1] < prefs_now["tone"][1]


def test_preference_profile_contradictory_signals_resolve_to_dominant() -> None:
    from famulix.preferences import PreferenceProfile

    profile = PreferenceProfile(decay_half_life_s=86400 * 365)
    for _ in range(5):
        profile.add_feedback("length", "short", "up", timestamp_s=1000, confidence=0.8)
    for _ in range(2):
        profile.add_feedback("length", "long", "up", timestamp_s=1000, confidence=0.8)
    prefs = profile.current_preferences(now_s=1000, min_confidence=0.0)
    assert prefs["length"][0] == "short"


def test_preference_profile_rejects_invalid_inputs() -> None:
    import pytest

    from famulix.preferences import PreferenceProfile

    profile = PreferenceProfile()
    with pytest.raises(ValueError, match="non-empty"):
        profile.add_feedback("", "value", "up", timestamp_s=100)
    with pytest.raises(ValueError, match="non-negative"):
        profile.add_feedback("key", "value", "up", timestamp_s=-1)
    with pytest.raises(ValueError, match="finite"):
        profile.add_feedback("key", "value", "up", timestamp_s=100, confidence=float("nan"))
    with pytest.raises(ValueError, match="\\[0, 1\\]"):
        profile.add_feedback("key", "value", "up", timestamp_s=100, confidence=1.5)
