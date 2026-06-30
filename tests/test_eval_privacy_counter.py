"""Test evaluation privacy violation counter."""

from famulix.evaluation import count_privacy_violations


def test_privacy_counter_zero_when_clean():
    results = [
        {"tier": "private", "accessed_by": "private"},
        {"tier": "public", "accessed_by": "public"},
    ]

    violations = count_privacy_violations(results)

    assert violations == 0


def test_privacy_counter_detects_leaks():
    results = [
        {"tier": "private", "accessed_by": "public"},
        {"tier": "private", "accessed_by": "private"},
        {"tier": "confidential", "accessed_by": "public"},
    ]

    violations = count_privacy_violations(results)

    assert violations == 2


def test_privacy_counter_empty():
    violations = count_privacy_violations([])
    assert violations == 0
