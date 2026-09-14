"""Tests comparing knapsack DP against brute-force on small instances."""

from famulix.context import (
    ContextItem,
    brute_force_knapsack,
    knapsack_dp,
    total_value,
)


def _make_items(n: int) -> list[ContextItem]:
    return [
        ContextItem(
            item_id=f"item_{i}",
            payload=f"payload {i}",
            token_estimate=10 + (i % 7) * 5,
            value=0.5 + (i % 5) * 0.1,
        )
        for i in range(n)
    ]


def test_dp_matches_brute_force_small():
    items = _make_items(8)
    budget = 50
    dp_indices = knapsack_dp(items, budget)
    bf_indices = brute_force_knapsack(items, budget)
    dp_val = total_value(items, dp_indices)
    bf_val = total_value(items, bf_indices)
    assert abs(dp_val - bf_val) < 1e-9


def test_dp_matches_brute_force_tight_budget():
    items = _make_items(6)
    budget = 25
    dp_indices = knapsack_dp(items, budget)
    bf_indices = brute_force_knapsack(items, budget)
    dp_val = total_value(items, dp_indices)
    bf_val = total_value(items, bf_indices)
    assert abs(dp_val - bf_val) < 1e-9


def test_dp_never_exceeds_budget():
    items = _make_items(10)
    budget = 60
    dp_indices = knapsack_dp(items, budget)
    total_tokens = sum(items[i].token_estimate for i in dp_indices)
    assert total_tokens <= budget


def test_brute_force_never_exceeds_budget():
    items = _make_items(6)
    budget = 40
    bf_indices = brute_force_knapsack(items, budget)
    total_tokens = sum(items[i].token_estimate for i in bf_indices)
    assert total_tokens <= budget
