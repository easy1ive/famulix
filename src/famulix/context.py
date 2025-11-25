"""Context assembly: budgeted selection as 0/1 knapsack with DP.

Guarantees the assembled context never exceeds the token budget. Also
provides a greedy comparator so callers can verify the DP result is
optimal on small instances.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class ContextItem:
    """An item eligible for inclusion in the context window."""

    item_id: str
    token_estimate: int
    value: float  # salience / relevance score
    payload: str  # the text snippet
    metadata: dict[str, str] = field(default_factory=dict)


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


def brute_force_knapsack(items: Sequence[ContextItem], budget: int) -> list[int]:
    """Enumerate all subsets to find the true optimum.

    For verifying DP correctness on small instances (n <= ~20).
    """
    _validate_inputs(items, budget)
    n = len(items)
    if n == 0 or budget == 0:
        return []
    if n > 24:
        raise ValueError("brute force only intended for small instances (n <= 24)")

    best_value = -1.0
    best_mask = 0
    for mask in range(1 << n):
        total_w = 0
        total_v = 0.0
        valid = True
        for i in range(n):
            if mask & (1 << i):
                total_w += items[i].token_estimate
                total_v += items[i].value
                if total_w > budget:
                    valid = False
                    break
        if valid and total_v > best_value:
            best_value = total_v
            best_mask = mask

    selected: list[int] = []
    for i in range(n):
        if best_mask & (1 << i):
            selected.append(i)
    return selected


def total_value(items: Sequence[ContextItem], indices: list[int]) -> float:
    return round(sum(items[i].value for i in indices), 6)


def total_weight(items: Sequence[ContextItem], indices: list[int]) -> int:
    return sum(items[i].token_estimate for i in indices)


def trim_to_budget(items: Sequence[ContextItem], budget: int) -> list[ContextItem]:
    """Drop the lowest-value items until the sequence fits the budget.

    A conservative fallback for pre-ordered context lists: unlike the
    knapsack it never reorders survivors or picks a heavier mix, it only
    removes the least valuable entries (ties broken by item_id) until the
    total token estimate fits. The result always satisfies
    ``sum(token_estimate) <= budget``.
    """
    _validate_inputs(items, budget)
    kept = list(items)
    total = sum(item.token_estimate for item in kept)
    drop_order = sorted(range(len(kept)), key=lambda i: (kept[i].value, kept[i].item_id))
    dropped: set[int] = set()
    for index in drop_order:
        if total <= budget:
            break
        dropped.add(index)
        total -= kept[index].token_estimate
    return [item for i, item in enumerate(kept) if i not in dropped]


def order_context_items(
    items: list[ContextItem],
    *,
    strategy: str = "value_desc",
) -> list[ContextItem]:
    """Order context items by a specified strategy.

    Strategies:
    - "value_desc": highest value first (default)
    - "value_asc": lowest value first
    - "recency_desc": most recent first (by created_at_s in metadata)
    - "recency_asc": oldest first
    - "id_asc": alphabetical by item_id
    - "original": preserve input order
    """
    if strategy == "original":
        return list(items)
    elif strategy == "value_desc":
        return sorted(items, key=lambda x: (-x.value, x.item_id))
    elif strategy == "value_asc":
        return sorted(items, key=lambda x: (x.value, x.item_id))
    elif strategy == "recency_desc":
        return sorted(
            items,
            key=lambda x: (
                -int(x.metadata.get("created_at_s", "0")),
                x.item_id,
            ),
        )
    elif strategy == "recency_asc":
        return sorted(
            items,
            key=lambda x: (
                int(x.metadata.get("created_at_s", "0")),
                x.item_id,
            ),
        )
    elif strategy == "id_asc":
        return sorted(items, key=lambda x: x.item_id)
    else:
        raise ValueError(f"unknown ordering strategy: {strategy}")


def assemble_ordered_context(
    items: list[ContextItem],
    budget: int,
    *,
    order_strategy: str = "value_desc",
) -> list[ContextItem]:
    """Assemble context with explicit ordering before budget trimming.

    Items are first ordered by the strategy, then trimmed to fit the budget
    using the conservative drop-lowest approach. This ensures the ordering
    preference is respected in the final output.
    """
    ordered = order_context_items(items, strategy=order_strategy)
    return trim_to_budget(ordered, budget)
