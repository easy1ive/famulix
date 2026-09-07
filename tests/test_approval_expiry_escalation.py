"""Tests for approval queue expiry and escalation chain behavior."""

import pytest

from famulix.approval import ApprovalQueue, ApprovalRequest


@pytest.fixture
def queue_with_pending():
    q = ApprovalQueue()
    q.submit(
        ApprovalRequest(
            request_id="req_1",
            action="delete_memory",
            resource="mem_abc",
            requester="user",
            expires_at_s=2000,
        )
    )
    q.submit(
        ApprovalRequest(
            request_id="req_2",
            action="export_data",
            resource="graph",
            requester="user",
            expires_at_s=3000,
        )
    )
    return q


def test_expire_stale_removes_expired(queue_with_pending):
    q = queue_with_pending
    expired = q.expire_stale(now_s=2500)
    assert expired == 1
    assert q.pending_count() == 1


def test_expire_stale_none_expired(queue_with_pending):
    q = queue_with_pending
    expired = q.expire_stale(now_s=1000)
    assert expired == 0
    assert q.pending_count() == 2


def test_expire_stale_all_expired(queue_with_pending):
    q = queue_with_pending
    expired = q.expire_stale(now_s=5000)
    assert expired == 2
    assert q.pending_count() == 0


def test_escalation_metrics_empty():
    q = ApprovalQueue()
    metrics = q.escalation_metrics()
    assert metrics["pending"] == 0
    assert metrics["total"] == 0


def test_escalation_metrics_with_pending(queue_with_pending):
    q = queue_with_pending
    metrics = q.escalation_metrics()
    assert metrics["total"] == 2
    assert metrics["pending"] == 2


def test_expired_count_after_expiry(queue_with_pending):
    q = queue_with_pending
    q.expire_stale(now_s=2500)
    assert q.expired_count() == 1


def test_expired_metrics_after_expiry(queue_with_pending):
    q = queue_with_pending
    q.expire_stale(now_s=5000)
    metrics = q.escalation_metrics()
    assert metrics["expired"] == 2
