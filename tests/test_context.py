"""Tests for context assembly and knapsack DP."""

from __future__ import annotations

import pytest

from famulix.context import (
    AssemblyResult,
    ContextItem,
    assemble_context,
    estimate_tokens,
    knapsack_dp,
    knapsack_greedy,
    total_value,
    total_weight,
)


def _item(i: int, w: int, v: float) -> ContextItem:
    return ContextItem(item_id=f"item_{i}", token_estimate=w, value=v, payload=f"payload {i}")


def test_estimate_tokens_empty() -> None:
    assert estimate_tokens("") == 0


def test_estimate_tokens_ceil() -> None:
    # 4 chars → 1 token, 5 chars → 2 tokens
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_estimate_tokens_at_least_one_for_text() -> None:
    assert estimate_tokens("x") == 1


def test_knapsack_dp_empty() -> None:
    assert knapsack_dp([], 100) == []
    assert knapsack_dp([_item(1, 10, 1.0)], 0) == []


def test_knapsack_dp_single_item_fits() -> None:
    items = [_item(1, 10, 1.0)]
    selected = knapsack_dp(items, 100)
    assert selected == [0]
    assert total_value(items, selected) == pytest.approx(1.0)
    assert total_weight(items, selected) == 10


def test_knapsack_dp_single_item_too_heavy() -> None:
    items = [_item(1, 100, 1.0)]
    assert knapsack_dp(items, 50) == []


def test_knapsack_dp_classic_knapsack() -> None:
    # Classic test: weights [2,3,4,5], values [3,4,5,6], budget=5
    # Optimal: item 0 + item 1 = weight 5, value 7
    items = [
        _item(0, 2, 3.0),
        _item(1, 3, 4.0),
        _item(2, 4, 5.0),
        _item(3, 5, 6.0),
    ]
    selected = knapsack_dp(items, 5)
    val = total_value(items, selected)
    wt = total_weight(items, selected)
    assert wt <= 5
    assert val == pytest.approx(7.0)


def test_knapsack_dp_vs_brute_force_small() -> None:
    """Property test: DP matches brute force on small random instances."""
    import random

    rng = random.Random(42)
    for _ in range(20):
        n = rng.randint(1, 8)
        items = [_item(i, rng.randint(1, 20), round(rng.random() * 10, 4)) for i in range(n)]
        budget = rng.randint(5, 50)
        dp_val = total_value(items, knapsack_dp(items, budget))
        # Brute force
        best_val = 0.0
        for mask in range(1 << n):
            selected = [i for i in range(n) if mask & (1 << i)]
            wt = total_weight(items, selected)
            if wt <= budget:
                best_val = max(best_val, total_value(items, selected))
        assert dp_val == pytest.approx(best_val, rel=1e-6)


def test_knapsack_greedy_never_beats_dp() -> None:
    """DP result should have >= value than greedy on any instance."""
    import random

    rng = random.Random(123)
    for _ in range(30):
        n = rng.randint(3, 12)
        items = [_item(i, rng.randint(1, 30), round(rng.random() * 10, 4)) for i in range(n)]
        budget = rng.randint(10, 80)
        dp_val = total_value(items, knapsack_dp(items, budget))
        greedy_val = total_value(items, knapsack_greedy(items, budget))
        assert dp_val >= greedy_val - 1e-9


def test_assemble_context_within_budget() -> None:
    items = [_item(i, w, float(w)) for i, w in enumerate([10, 20, 30, 40, 50])]
    result = assemble_context(items, budget=75)
    assert result.within_budget
    assert result.total_tokens <= 75


def test_assemble_context_never_exceeds_budget() -> None:
    """Stress test: result is always within budget."""
    import random

    rng = random.Random(99)
    for _ in range(50):
        items = [
            _item(i, rng.randint(1, 50), round(rng.random() * 100, 4))
            for i in range(rng.randint(2, 15))
        ]
        budget = rng.randint(20, 200)
        result = assemble_context(items, budget=budget)
        assert result.total_tokens <= budget


def test_assemble_context_greedy_mode() -> None:
    items = [_item(i, w, float(w)) for i, w in enumerate([10, 20, 30])]
    result = assemble_context(items, budget=25, use_dp=False)
    assert result.within_budget
    assert result.total_tokens <= 25


def test_assembly_result_render() -> None:
    items = [_item(0, 10, 1.0), _item(1, 20, 2.0)]
    result = assemble_context(items, budget=100)
    rendered = result.render()
    assert "item_0" in rendered
    assert "item_1" in rendered


def test_assembly_result_is_sorted_by_value_desc() -> None:
    items = [
        _item(0, 10, 1.0),
        _item(1, 20, 3.0),
        _item(2, 15, 2.0),
    ]
    result = assemble_context(items, budget=100)
    values = [it.value for it in result.items]
    assert values == sorted(values, reverse=True)


def test_assembly_result_type() -> None:
    items = [_item(0, 10, 1.0)]
    result = assemble_context(items, budget=100)
    assert isinstance(result, AssemblyResult)
    assert isinstance(result.items, list)
    assert len(result.items) == 1


def test_assembly_rejects_invalid_budget_and_item_scores() -> None:
    with pytest.raises(ValueError, match="budget"):
        assemble_context([], budget=-1)
    with pytest.raises(ValueError, match="positive integers"):
        assemble_context([_item(1, 0, 1.0)], budget=10)
    with pytest.raises(ValueError, match="finite and non-negative"):
        assemble_context([_item(1, 2, float("inf"))], budget=10)


def test_dp_matches_brute_force_randomized_small() -> None:
    """DP optimal value equals brute-force optimum on 50 random small instances."""
    import random

    from famulix.context import brute_force_knapsack, total_value

    rng = random.Random(42)
    for _ in range(50):
        n = rng.randint(1, 10)
        items = [_item(i, rng.randint(1, 20), round(rng.uniform(0.1, 5.0), 3)) for i in range(n)]
        budget = rng.randint(5, 80)
        dp_indices = knapsack_dp(items, budget)
        bf_indices = brute_force_knapsack(items, budget)
        assert total_value(items, dp_indices) == pytest.approx(total_value(items, bf_indices))


def test_brute_force_knapsack_respects_budget() -> None:
    from famulix.context import brute_force_knapsack, total_weight

    items = [_item(i, w, float(w)) for i, w in enumerate([3, 5, 7, 11])]
    indices = brute_force_knapsack(items, budget=10)
    assert total_weight(items, indices) <= 10
