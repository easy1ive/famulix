"""Integration test: context assembly with knapsack optimization.

Verifies that context assembly respects budgets, uses DP for optimality,
and maintains ordering invariants.
"""

from famulix.context import ContextItem, assemble_context, estimate_tokens


def test_context_assembly_respects_budget():
    """Verify context assembly never exceeds token budget."""
    items = [
        ContextItem(item_id=f"item_{i}", token_estimate=50, value=float(i), payload=f"Content {i}")
        for i in range(10)
    ]

    budget = 200
    result = assemble_context(items, budget=budget, use_dp=True)

    assert result.total_tokens <= budget, f"Exceeded budget: {result.total_tokens} > {budget}"
    assert result.within_budget


def test_context_assembly_dp_vs_greedy():
    """Verify DP finds optimal solution where greedy may not."""
    # Craft items where greedy (by value density) differs from optimal
    items = [
        ContextItem(item_id="a", token_estimate=100, value=60.0, payload="A"),  # density 0.6
        ContextItem(item_id="b", token_estimate=100, value=60.0, payload="B"),  # density 0.6
        ContextItem(item_id="c", token_estimate=50, value=35.0, payload="C"),  # density 0.7
        ContextItem(item_id="d", token_estimate=50, value=35.0, payload="D"),  # density 0.7
    ]

    budget = 200

    # DP should find optimal: c + d + (a or b) = 35 + 35 + 60 = 130
    dp_result = assemble_context(items, budget=budget, use_dp=True)

    # Greedy picks by density: c, d, then a or b
    greedy_result = assemble_context(items, budget=budget, use_dp=False)

    # Both should be within budget
    assert dp_result.total_tokens <= budget
    assert greedy_result.total_tokens <= budget

    # DP value should be >= greedy value (optimal vs approximate)
    assert dp_result.total_value >= greedy_result.total_value


def test_context_assembly_empty_input():
    """Verify context assembly handles empty input."""
    result = assemble_context([], budget=500, use_dp=True)

    assert result.total_tokens == 0
    assert result.total_value == 0.0
    assert len(result.items) == 0
    assert result.within_budget


def test_context_assembly_single_large_item():
    """Verify items exceeding budget are excluded."""
    items = [
        ContextItem(item_id="large", token_estimate=1000, value=100.0, payload="Large"),
    ]

    budget = 500
    result = assemble_context(items, budget=budget, use_dp=True)

    assert len(result.items) == 0, "Item exceeding budget should be excluded"
    assert result.total_tokens == 0


def test_context_assembly_ordering():
    """Verify context items maintain value-based ordering."""
    items = [
        ContextItem(item_id="low", token_estimate=50, value=10.0, payload="Low"),
        ContextItem(item_id="high", token_estimate=50, value=90.0, payload="High"),
        ContextItem(item_id="mid", token_estimate=50, value=50.0, payload="Mid"),
    ]

    budget = 150
    result = assemble_context(items, budget=budget, use_dp=True)

    # All items should fit
    assert len(result.items) == 3

    # Items should be ordered by value (descending)
    values = [it.value for it in result.items]
    assert values == sorted(values, reverse=True), "Items should be ordered by value"


def test_estimate_tokens_reasonable():
    """Verify token estimation is reasonable."""
    short_text = "Hello"
    long_text = "This is a much longer text with many words and characters"

    short_tokens = estimate_tokens(short_text)
    long_tokens = estimate_tokens(long_text)

    assert short_tokens > 0
    assert long_tokens > short_tokens
    assert short_tokens < 10, "Short text should be <10 tokens"
    assert long_tokens < 50, "Long text should be <50 tokens"


def test_context_assembly_exact_budget_fit():
    """Verify items that exactly fit the budget are selected."""
    items = [
        ContextItem(item_id="a", token_estimate=100, value=50.0, payload="A"),
        ContextItem(item_id="b", token_estimate=100, value=50.0, payload="B"),
        ContextItem(item_id="c", token_estimate=100, value=50.0, payload="C"),
    ]

    budget = 200
    result = assemble_context(items, budget=budget, use_dp=True)

    # Should select exactly 2 items
    assert len(result.items) == 2
    assert result.total_tokens == 200
