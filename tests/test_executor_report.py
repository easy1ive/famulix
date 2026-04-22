"""Test execution report formatting."""

from famulix.executor import ExecutionState, StepExecution, format_execution_report


def test_format_execution_report_success():
    """Verify report for successful execution."""
    state = ExecutionState()
    state.history.append(StepExecution(step_id="step1", success=True, error=None))
    state.history.append(StepExecution(step_id="step2", success=True, error=None))
    state.steps_done = 2
    state.tokens_used = 300
    state.money_spent = 0.03

    report = format_execution_report(state)

    assert "# Plan Execution Report" in report
    assert "## Summary" in report
    assert "**Steps completed**: 2" in report
    assert "**Successes**: 2" in report
    assert "**Failures**: 0" in report
    assert "**Tokens used**: 300" in report
    assert "**Money spent**: $0.0300" in report
    assert "## Step Details" in report
    assert "Step step1 ✓" in report
    assert "Step step2 ✓" in report


def test_format_execution_report_with_failures():
    """Verify report includes failure details."""
    state = ExecutionState()
    state.history.append(StepExecution(step_id="step1", success=True, error=None))
    state.history.append(StepExecution(step_id="step2", success=False, error="Timeout exceeded"))
    state.steps_done = 2
    state.tokens_used = 100
    state.money_spent = 0.01
    state.terminated = True
    state.termination_reason = "Step failure"

    report = format_execution_report(state)

    assert "**Failures**: 1" in report
    assert "**Terminated**: True" in report
    assert "**Termination reason**: Step failure" in report
    assert "Step step1 ✓" in report
    assert "Step step2 ✗" in report
    assert "**Error**: Timeout exceeded" in report


def test_format_execution_report_empty():
    """Verify report for empty execution."""
    state = ExecutionState()

    report = format_execution_report(state)

    assert "# Plan Execution Report" in report
    assert "**Steps completed**: 0" in report
    assert "**Successes**: 0" in report
    assert "**Failures**: 0" in report
