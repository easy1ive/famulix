"""Context assembly: budgeted selection as 0/1 knapsack with DP.

Guarantees the assembled context never exceeds the token budget. Also
provides a greedy comparator so callers can verify the DP result is
optimal on small instances.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ContextItem:
    """An item eligible for inclusion in the context window."""

    item_id: str
    token_estimate: int
    value: float  # salience / relevance score
    payload: str  # the text snippet


@dataclass(frozen=True)
class AssemblyResult:
    """Result of context assembly."""

    items: list[ContextItem]
    total_tokens: int
    total_value: float
    budget: int

    @property
    def within_budget(self) -> bool:
        return self.total_tokens <= self.budget

    def render(self) -> str:
        parts = []
        for item in self.items:
            parts.append(f"[{item.item_id}] {item.payload}")
        return "\n\n".join(parts)


def estimate_tokens(text: str) -> int:
    """Rough token estimator: ~4 chars per token for English text.

    Conservative upper bound ensures we never exceed budget.
    """
    if not text:
        return 0
    return max(1, int(np.ceil(len(text) / 4.0)))


def _validate_inputs(items: Sequence[ContextItem], budget: int) -> None:
    if type(budget) is not int or budget < 0:
        raise ValueError("budget must be a non-negative integer")
    for item in items:
        if type(item.token_estimate) is not int or item.token_estimate <= 0:
            raise ValueError("context item token estimates must be positive integers")
        if not math.isfinite(item.value) or item.value < 0:
            raise ValueError("context item values must be finite and non-negative")


def knapsack_dp(items: Sequence[ContextItem], budget: int) -> list[int]:
    """0/1 knapsack exact DP. Returns indices of selected items.

    Maximizes value subject to total weight <= budget.
    Returns the list of selected indices in arbitrary order.
    """
    _validate_inputs(items, budget)
    n = len(items)
    if n == 0 or budget == 0:
        return []

    weights = [it.token_estimate for it in items]
    values = [it.value for it in items]

    # DP table: dp[j] = max value achievable with budget j
    dp = np.zeros(budget + 1, dtype=np.float64)
    # Track selection: keep bitmask per state
    # Use a 1D value array + backtracking via keep matrix
    keep = np.zeros((n + 1, budget + 1), dtype=bool)

    for i in range(1, n + 1):
        w = weights[i - 1]
        v = values[i - 1]
        # Iterate backwards to avoid reusing items
        for j in range(budget, w - 1, -1):
            if dp[j - w] + v > dp[j]:
                dp[j] = dp[j - w] + v
                keep[i, j] = True

    # Backtrack
    selected: list[int] = []
    j = budget
    for i in range(n, 0, -1):
        if keep[i, j]:
            selected.append(i - 1)
            j -= weights[i - 1]
    return selected


def knapsack_greedy(items: Sequence[ContextItem], budget: int) -> list[int]:
    """Greedy approximation: sort by value/weight density, take until budget full.

    Used as a comparator to sanity-check DP results (DP should never underperform
    greedy on any instance).
    """
    _validate_inputs(items, budget)
    if not items or budget == 0:
        return []
    indices = list(range(len(items)))
    # Sort by value/weight ratio, descending
    indices.sort(
        key=lambda i: items[i].value / max(items[i].token_estimate, 1),
        reverse=True,
    )
    selected: list[int] = []
    used = 0
    for idx in indices:
        w = items[idx].token_estimate
        if used + w <= budget:
            selected.append(idx)
            used += w
    return selected


def assemble_context(
    items: list[ContextItem],
    *,
    budget: int,
    use_dp: bool = True,
) -> AssemblyResult:
    """Assemble a context window within the token budget.

    By default uses exact DP for optimality. Set use_dp=False for greedy.
    """
    _validate_inputs(items, budget)
    # Filter out items that exceed the budget entirely
    eligible = [it for it in items if it.token_estimate <= budget]

    if use_dp:
        selected_indices = knapsack_dp(eligible, budget)
    else:
        selected_indices = knapsack_greedy(eligible, budget)

    selected_items = [eligible[i] for i in selected_indices]
    total_tokens = sum(it.token_estimate for it in selected_items)
    total_value = round(sum(it.value for it in selected_items), 6)

    # Enforce ordering: higher value first
    selected_items.sort(key=lambda it: it.value, reverse=True)

    return AssemblyResult(
        items=selected_items,
        total_tokens=total_tokens,
        total_value=total_value,
        budget=budget,
    )


def total_value(items: Sequence[ContextItem], indices: list[int]) -> float:
    return round(sum(items[i].value for i in indices), 6)


def total_weight(items: Sequence[ContextItem], indices: list[int]) -> int:
    return sum(items[i].token_estimate for i in indices)
