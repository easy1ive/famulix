"""Tests for approval queue."""

from __future__ import annotations

from famulix.approval import ApprovalQueue, ApprovalRequest


def test_submit_and_pending() -> None:
    q = ApprovalQueue()
    req = ApprovalRequest(
        request_id="r1",
        requester="alice",
        action="read",
        resource="mem/1",
        created_at_s=100,
        expires_at_s=200,
    )
    q.submit(req)
    assert len(q.pending()) == 1
    assert q.get("r1") is not None


def test_get_missing() -> None:
    q = ApprovalQueue()
    assert q.get("nonexistent") is None


def test_approve() -> None:
    q = ApprovalQueue()
    req = ApprovalRequest(
        request_id="r1", requester="alice", action="read", resource="mem/1", created_at_s=100
    )
    q.submit(req)
    result = q.decide("r1", "approved", approver="bob", decided_at_s=200)
    assert result is True
    assert q.get("r1").status == "approved"
    assert q.get("r1").approver == "bob"


def test_deny() -> None:
    q = ApprovalQueue()
    req = ApprovalRequest(
        request_id="r1", requester="alice", action="read", resource="mem/1", created_at_s=100
    )
    q.submit(req)
    q.decide("r1", "denied", approver="bob", decided_at_s=200)
    assert q.get("r1").status == "denied"


def test_decide_on_nonpending_noop() -> None:
    q = ApprovalQueue()
    req = ApprovalRequest(
        request_id="r1", requester="a", action="r", resource="x", created_at_s=100
    )
    q.submit(req)
    q.decide("r1", "approved", "bob", 200)
    # Try to decide again
    result = q.decide("r1", "denied", "charlie", 300)
    assert result is False
    assert q.get("r1").status == "approved"


def test_expire_stale() -> None:
    q = ApprovalQueue()
    req = ApprovalRequest(
        request_id="r1", requester="a", action="r", resource="x", created_at_s=100, expires_at_s=200
    )
    q.submit(req)
    expired = q.expire_stale(now_s=150)
    assert expired == 0
    assert len(q.pending()) == 1
    expired = q.expire_stale(now_s=250)
    assert expired == 1
    assert q.get("r1").status == "expired"
    assert len(q.pending()) == 0


def test_auto_approve_persona() -> None:
    q = ApprovalQueue()
    for i in range(3):
        q.submit(
            ApprovalRequest(
                request_id=f"r{i}", requester="a", action="r", resource="x", created_at_s=100
            )
        )
    count = q.auto_decide("auto_approve", now_s=200)
    assert count == 3
    assert all(r.status == "approved" for r in q.requests)


def test_auto_deny_persona() -> None:
    q = ApprovalQueue()
    q.submit(
        ApprovalRequest(request_id="r1", requester="a", action="r", resource="x", created_at_s=100)
    )
    count = q.auto_decide("auto_deny", now_s=200)
    assert count == 1
    assert q.get("r1").status == "denied"


def test_ask_human_persona_does_nothing() -> None:
    q = ApprovalQueue()
    q.submit(
        ApprovalRequest(request_id="r1", requester="a", action="r", resource="x", created_at_s=100)
    )
    count = q.auto_decide("ask_human", now_s=200)
    assert count == 0
    assert q.get("r1").status == "pending"


def test_escalation_metrics() -> None:
    q = ApprovalQueue()
    q.submit(
        ApprovalRequest(request_id="r1", requester="a", action="r", resource="x", created_at_s=100)
    )
    q.submit(
        ApprovalRequest(request_id="r2", requester="a", action="r", resource="x", created_at_s=100)
    )
    q.submit(
        ApprovalRequest(request_id="r3", requester="a", action="r", resource="x", created_at_s=100)
    )
    q.decide("r1", "approved", "bob", 200)
    q.decide("r2", "denied", "bob", 200)
    metrics = q.escalation_metrics()
    assert metrics["total"] == 3
    assert metrics["pending"] == 1
    assert metrics["approved"] == 1
    assert metrics["denied"] == 1
    assert metrics["expired"] == 0


def test_approval_queue_count_helpers() -> None:
    from famulix.approval import ApprovalQueue, ApprovalRequest

    q = ApprovalQueue()
    assert q.total_count() == 0
    assert q.pending_count() == 0
    assert q.has_pending() is False

    q.submit(
        ApprovalRequest(request_id="r1", requester="a", action="r", resource="x", created_at_s=100)
    )
    q.submit(
        ApprovalRequest(request_id="r2", requester="a", action="r", resource="x", created_at_s=100)
    )
    assert q.total_count() == 2
    assert q.pending_count() == 2
    assert q.has_pending() is True

    q.decide("r1", "approved", "bob", 200)
    assert q.total_count() == 2
    assert q.pending_count() == 1
    assert q.has_pending() is True

    q.decide("r2", "denied", "bob", 200)
    assert q.total_count() == 2
    assert q.pending_count() == 0
    assert q.has_pending() is False
