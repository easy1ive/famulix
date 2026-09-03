"""Performance test: context assembly time with large item sets."""

import time

from famulix.context import ContextItem, assemble_context


def _make_items(n: int) -> list[ContextItem]:
    return [
        ContextItem(
            item_id=f"mem_{i:04d}",
            payload=f"Memory content for item {i} with some text",
            token_estimate=10 + (i % 5),
            value=0.5 + (i % 100) / 200.0,
        )
        for i in range(n)
    ]


def test_context_assembly_100_items():
    items = _make_items(100)
    start = time.monotonic()
    result = assemble_context(items, budget=500)
    elapsed_ms = (time.monotonic() - start) * 1000
    assert result.within_budget
    assert elapsed_ms < 5000, f"context assembly 100 items: {elapsed_ms:.0f}ms"


def test_context_assembly_500_items():
    items = _make_items(500)
    start = time.monotonic()
    result = assemble_context(items, budget=1000)
    elapsed_ms = (time.monotonic() - start) * 1000
    assert result.within_budget
    assert elapsed_ms < 15000, f"context assembly 500 items: {elapsed_ms:.0f}ms"


def test_context_assembly_deterministic():
    items = _make_items(50)
    r1 = assemble_context(items, budget=300)
    r2 = assemble_context(items, budget=300)
    assert r1.total_value == r2.total_value
    assert r1.total_tokens == r2.total_tokens
