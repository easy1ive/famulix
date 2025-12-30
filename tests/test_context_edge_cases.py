"""Edge case tests for context assembly."""

import pytest

from famulix.context import ContextItem, assemble_context


def test_assemble_empty_items():
    """Empty item list should produce empty result."""
    result = assemble_context([], budget=500)
    assert result.items == []
    assert result.total_value == 0.0


def test_assemble_zero_budget():
    """Zero budget should select nothing."""
    items = [ContextItem(item_id="1", payload="text", value=1.0, token_estimate=10)]
    result = assemble_context(items, budget=0)
    assert result.items == []


def test_assemble_single_item_fits():
    """Single item that fits should be selected."""
    items = [ContextItem(item_id="1", payload="text", value=1.0, token_estimate=10)]
    result = assemble_context(items, budget=100)
    assert len(result.items) == 1


def test_assemble_single_item_too_large():
    """Single item too large should not be selected."""
    items = [ContextItem(item_id="1", payload="text", value=1.0, token_estimate=1000)]
    result = assemble_context(items, budget=100)
    assert result.items == []


def test_assemble_negative_budget_rejected():
    """Negative budget should be rejected."""
    items = [ContextItem(item_id="1", payload="text", value=1.0, token_estimate=10)]
    with pytest.raises(ValueError):
        assemble_context(items, budget=-1)
