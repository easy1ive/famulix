"""Tests for execution budget enforcement: step/token/money limits."""

from famulix.executor import ExecutionBudget, ExecutionState


def test_budget_creation():
    budget = ExecutionBudget(max_steps=10, max_tokens=5000, max_money=100.0)
    assert budget.max_steps == 10
    assert budget.max_tokens == 5000


def test_state_tracks_steps():
    state = ExecutionState()
    assert state.step_count() == 0
    assert state.tokens_used == 0


def test_budget_validation():
    import pytest

    with pytest.raises(ValueError):
        ExecutionBudget(max_steps=-1)
    with pytest.raises(ValueError):
        ExecutionBudget(max_tokens=-100)


def test_budget_deterministic():
    b1 = ExecutionBudget(max_steps=5, max_tokens=1000, max_money=50.0)
    b2 = ExecutionBudget(max_steps=5, max_tokens=1000, max_money=50.0)
    assert b1.max_steps == b2.max_steps
    assert b1.max_tokens == b2.max_tokens
    assert b1.max_money == b2.max_money


def test_state_outputs_dict():
    state = ExecutionState()
    state.outputs["result"] = "value"
    assert state.outputs["result"] == "value"
