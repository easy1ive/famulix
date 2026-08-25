"""Tests for preference calibration reliability bins and error measurement."""

import pytest

from famulix.preferences import (
    brier_score,
    calibration_error,
    reliability_bins,
)


def test_reliability_bins_perfect_calibration():
    """Predictions that match outcomes exactly should show perfect calibration."""
    predictions = [0.1, 0.2, 0.8, 0.9]
    outcomes = [0, 0, 1, 1]
    bins = reliability_bins(predictions, outcomes, n_bins=2)
    assert len(bins) == 2
    for b in bins:
        assert abs(b["avg_predicted"] - b["avg_observed"]) < 0.3


def test_reliability_bins_count():
    predictions = [0.1, 0.3, 0.5, 0.7, 0.9]
    outcomes = [0, 0, 1, 1, 1]
    bins = reliability_bins(predictions, outcomes, n_bins=3)
    assert len(bins) == 3


def test_reliability_bins_deterministic():
    preds = [0.2, 0.4, 0.6, 0.8]
    outs = [0, 0, 1, 1]
    b1 = reliability_bins(preds, outs, n_bins=2)
    b2 = reliability_bins(preds, outs, n_bins=2)
    assert b1 == b2


def test_brier_score_perfect():
    predictions = [0.0, 1.0, 1.0]
    outcomes = [0, 1, 1]
    assert brier_score(predictions, outcomes) == 0.0


def test_brier_score_worst():
    predictions = [1.0, 0.0]
    outcomes = [0, 1]
    assert brier_score(predictions, outcomes) == 1.0


def test_brier_score_bounded():
    import random

    rng = random.Random(42)
    preds = [rng.random() for _ in range(50)]
    outs = [rng.randint(0, 1) for _ in range(50)]
    score = brier_score(preds, outs)
    assert 0.0 <= score <= 1.0


def test_calibration_error_perfect():
    predictions = [0.0, 0.5, 1.0]
    outcomes = [0, 0, 1]
    error = calibration_error(predictions, outcomes, n_bins=2)
    assert error < 0.5


def test_calibration_error_validates_inputs():
    with pytest.raises(ValueError):
        brier_score([1.5], [0])
    with pytest.raises(ValueError):
        brier_score([0.5], [2])
