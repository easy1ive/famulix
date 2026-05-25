"""Integration test: approval queue and plan DSL.

Verifies that approval queue handles expiry and decisions, and plan DAG
validation detects cycles and dangling references.
"""

from famulix.approval import ApprovalQueue, ApprovalRequest
from famulix.plan_dsl import Plan, PlanStep, validate_plan


def test_approval_queue_expiry():
    """Verify approval requests expire correctly."""
    queue = ApprovalQueue()

    # Add a request with 1-hour expiry
    req = ApprovalRequest(
        request_id="req-001",
        requester="system",
        action="send_email",
        resource="user@example.com",
        expires_at_s=1000000 + 3600,
    )
    queue.submit(req)

    # Before expiry, should be pending
    pending = queue.pending()
    assert len(pending) == 1
    assert pending[0].request_id == "req-001"

    # After expiry, should be marked expired
    expired_count = queue.expire_stale(now_s=1000000 + 7200)
    assert expired_count == 1

    # Should no longer be pending
    pending_after = queue.pending()
    assert len(pending_after) == 0


def test_approval_queue_decision():
    """Verify approval decisions are recorded correctly."""
    queue = ApprovalQueue()

    req = ApprovalRequest(
        request_id="req-002",
        requester="system",
        action="delete_memory",
        resource="mem_123",
        expires_at_s=1000000 + 3600,
    )
    queue.submit(req)

    # Approve the request
    success = queue.decide(
        "req-002", decision="approved", approver="admin", decided_at_s=1000000 + 100
    )
    assert success, "Decision should succeed"

    # Should no longer be pending
    pending = queue.pending()
    assert len(pending) == 0

    # Decision should be recorded
    decided_req = queue.get("req-002")
    assert decided_req is not None
    assert decided_req.status == "approved"
    assert decided_req.approver == "admin"


def test_plan_dag_validation_no_cycles():
    """Verify plan DAG validation accepts valid plans."""
    steps = [
        PlanStep(id="a", tool="recall", inputs={}, depends_on=[]),
        PlanStep(id="b", tool="brief", inputs={}, depends_on=["a"]),
        PlanStep(id="c", tool="export", inputs={}, depends_on=["b"]),
    ]

    plan = Plan(plan_id="test-plan", steps=steps)
    result = validate_plan(plan)
    assert result.valid, f"Valid plan should pass: {result.errors}"


def test_plan_dag_validation_detects_cycles():
    """Verify plan DAG validation detects cycles."""
    steps = [
        PlanStep(id="a", tool="recall", inputs={}, depends_on=["c"]),
        PlanStep(id="b", tool="brief", inputs={}, depends_on=["a"]),
        PlanStep(id="c", tool="export", inputs={}, depends_on=["b"]),
    ]

    plan = Plan(plan_id="cyclic-plan", steps=steps)
    result = validate_plan(plan)
    assert not result.valid, "Cyclic plan should fail validation"
    assert any("cycle" in e.lower() for e in result.errors), "Should detect cycle"


def test_plan_dag_validation_dangling_refs():
    """Verify plan DAG validation detects dangling references."""
    steps = [
        PlanStep(id="a", tool="recall", inputs={}, depends_on=["nonexistent"]),
    ]

    plan = Plan(plan_id="dangling-plan", steps=steps)
    result = validate_plan(plan)
    assert not result.valid, "Plan with dangling refs should fail"
    assert any(
        "dangling" in e.lower() or "missing" in e.lower() or "unknown" in e.lower()
        for e in result.errors
    ), f"Should detect dangling ref: {result.errors}"
