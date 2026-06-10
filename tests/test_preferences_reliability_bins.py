"""Test preference calibration reliability bins."""

from famulix.preferences import compute_reliability_bins


def test_reliability_bins_perfect_calibration():
    predictions = [(0.9, True), (0.9, True), (0.1, False), (0.1, False)]
    bins = compute_reliability_bins(predictions, n_bins=10)

    high_conf = [b for b in bins if b["confidence"] > 0.8]
    assert len(high_conf) > 0
    assert high_conf[0]["accuracy"] > 0.8


def test_reliability_bins_overconfidence():
    predictions = [(0.9, False), (0.9, False), (0.8, False), (0.8, True)]
    bins = compute_reliability_bins(predictions, n_bins=10)

    high_conf = [b for b in bins if b["confidence"] > 0.7]
    assert len(high_conf) > 0
    assert high_conf[0]["accuracy"] < high_conf[0]["confidence"]


def test_reliability_bins_empty():
    bins = compute_reliability_bins([], n_bins=10)
    assert bins == []
