"""Test approval expiry and escalation metrics."""

from famulix.approval import compute_approval_metrics


def test_approval_metrics_counts_expired():
    decisions = [
        {"approved": True, "latency_s": 10},
        {"approved": False, "latency_s": 5},
        {"expired": True, "latency_s": 3600},
    ]

    metrics = compute_approval_metrics(decisions)

    assert metrics["total"] == 3
    assert metrics["approved"] == 1
    assert metrics["denied"] == 1
    assert metrics["expired"] == 1


def test_approval_metrics_latency_stats():
    decisions = [
        {"approved": True, "latency_s": 10},
        {"approved": True, "latency_s": 20},
        {"approved": True, "latency_s": 30},
    ]

    metrics = compute_approval_metrics(decisions)

    assert metrics["avg_latency_s"] == 20.0
    assert metrics["min_latency_s"] == 10
    assert metrics["max_latency_s"] == 30


def test_approval_metrics_empty():
    metrics = compute_approval_metrics([])
    assert metrics["total"] == 0
