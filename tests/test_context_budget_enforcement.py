"""Test context assembly never exceeds budget."""

from famulix.context import ContextItem, assemble_context


def test_context_assembly_respects_budget():
    items = [
        ContextItem(
            item_id=f"item_{i}",
            token_estimate=50 + i,
            value=1.0 - i * 0.01,
            payload=f"Item {i} with some content",
        )
        for i in range(20)
    ]

    budget = 500

    result = assemble_context(items, budget=budget)

    assert result.total_tokens <= budget
    assert len(result.items) > 0


def test_context_assembly_empty_when_budget_zero():
    items = [
        ContextItem(
            item_id="item_1",
            token_estimate=50,
            value=1.0,
            payload="Some content",
        )
    ]

    result = assemble_context(items, budget=0)

    assert len(result.items) == 0
    assert result.total_tokens == 0
