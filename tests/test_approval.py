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


def test_approval_escalation_chain_moves_to_next_approver() -> None:
    from famulix.approval import ApprovalQueue, ApprovalRequest

    queue = ApprovalQueue()
    queue.escalation_chains["sensitive_action"] = ["manager", "director", "vp"]
    req = ApprovalRequest(
        request_id="r1",
        requester="user",
        action="sensitive_action",
        resource="data",
        created_at_s=100,
        expires_at_s=1000,
    )
    queue.submit(req)
    assert queue.escalate("r1", now_s=200)
    updated = queue.get("r1")
    assert updated is not None
    assert updated.escalation_level == 1
    assert updated.approver == "manager"
    assert queue.escalate("r1", now_s=300)
    updated2 = queue.get("r1")
    assert updated2 is not None
    assert updated2.escalation_level == 2
    assert updated2.approver == "director"


def test_approval_escalation_stops_at_chain_end() -> None:
    from famulix.approval import ApprovalQueue, ApprovalRequest

    queue = ApprovalQueue()
    queue.escalation_chains["action"] = ["level1"]
    req = ApprovalRequest(
        request_id="r1",
        requester="user",
        action="action",
        resource="res",
        created_at_s=100,
    )
    queue.submit(req)
    assert queue.escalate("r1", now_s=200)
    assert not queue.escalate("r1", now_s=300)
    updated = queue.get("r1")
    assert updated is not None
    assert updated.escalation_level == 1


def test_approval_expired_and_escalated_counts() -> None:
    from famulix.approval import ApprovalQueue, ApprovalRequest

    queue = ApprovalQueue()
    req1 = ApprovalRequest(
        request_id="r1", requester="u", action="a", resource="r", created_at_s=100, expires_at_s=200
    )
    req2 = ApprovalRequest(
        request_id="r2",
        requester="u",
        action="b",
        resource="r",
        created_at_s=100,
        escalation_level=2,
    )
    queue.submit(req1)
    queue.submit(req2)
    queue.expire_stale(now_s=300)
    assert queue.expired_count() == 1
    assert queue.escalated_count() == 1


def test_approval_average_decision_time() -> None:
    from famulix.approval import ApprovalQueue, ApprovalRequest

    queue = ApprovalQueue()
    req1 = ApprovalRequest(
        request_id="r1", requester="u", action="a", resource="r", created_at_s=100
    )
    req2 = ApprovalRequest(
        request_id="r2", requester="u", action="b", resource="r", created_at_s=200
    )
    queue.submit(req1)
    queue.submit(req2)
    queue.decide("r1", "approved", "admin", decided_at_s=150)
    queue.decide("r2", "denied", "admin", decided_at_s=300)
    avg = queue.average_decision_time()
    assert avg == 75.0


def test_add_escalation_chain_validates_input() -> None:
    import pytest

    from famulix.approval import ApprovalQueue

    queue = ApprovalQueue()
    queue.add_escalation_chain("deploy", ["alice", "bob"])
    assert queue.chain_depth("deploy") == 2

    with pytest.raises(ValueError, match="non-empty"):
        queue.add_escalation_chain("", ["alice"])
    with pytest.raises(ValueError, match="at least one"):
        queue.add_escalation_chain("deploy", [])
    with pytest.raises(ValueError, match="non-empty strings"):
        queue.add_escalation_chain("deploy", ["alice", ""])


def test_validate_chains_reports_problems() -> None:
    from famulix.approval import ApprovalQueue

    queue = ApprovalQueue()
    queue.escalation_chains[""] = ["alice"]
    queue.escalation_chains["deploy"] = []
    queue.escalation_chains["test"] = ["valid", ""]
    problems = queue.validate_chains()
    assert len(problems) == 3
    assert any("empty action" in p for p in problems)
    assert any("is empty" in p for p in problems)
    assert any("invalid approver" in p for p in problems)


def test_chain_depth_returns_zero_for_unknown() -> None:
    from famulix.approval import ApprovalQueue

    queue = ApprovalQueue()
    assert queue.chain_depth("unknown") == 0
    queue.add_escalation_chain("deploy", ["alice", "bob", "charlie"])
    assert queue.chain_depth("deploy") == 3


def test_escalate_uses_registered_chain() -> None:
    from famulix.approval import ApprovalQueue, ApprovalRequest

    queue = ApprovalQueue()
    queue.add_escalation_chain("deploy", ["manager", "director"])
    req = ApprovalRequest(
        request_id="r1",
        requester="dev",
        action="deploy",
        resource="production",
        status="pending",
        created_at_s=1000,
        expires_at_s=2000,
    )
    queue.submit(req)
    assert queue.escalate("r1", 1500)
    assert req.escalation_level == 1
    assert req.approver == "manager"
    assert queue.escalate("r1", 1600)
    assert req.escalation_level == 2
    assert req.approver == "director"
    assert not queue.escalate("r1", 1700)  # end of chain
