"""Test context assembly statistics."""

from famulix.context import AssemblyResult, ContextItem, context_assembly_stats


def test_assembly_stats():
    """Should extract assembly fields."""
    result = AssemblyResult(
        items=[ContextItem(item_id="1", payload="text", value=1.0, token_estimate=10)],
        total_tokens=10,
        total_value=1.0,
        budget=100,
    )
    stats = context_assembly_stats(result)
    assert stats["item_count"] == 1
    assert stats["total_tokens"] == 10
    assert stats["within_budget"] is True
