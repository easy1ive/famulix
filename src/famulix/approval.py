"""Approval queue: pending approvals with expiry, scripted personas, escalation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ApprovalStatus = Literal["pending", "approved", "denied", "expired", "escalated"]
ApproverPersona = Literal["auto_approve", "auto_deny", "ask_human"]


@dataclass
class ApprovalRequest:
    """A single pending approval."""

    request_id: str
    requester: str
    action: str
    resource: str
    reason: str = ""
    status: ApprovalStatus = "pending"
    created_at_s: int = 0
    expires_at_s: int = 0
    escalation_level: int = 0
    approver: str | None = None
    decided_at_s: int | None = None


@dataclass
class ApprovalQueue:
    """Approval queue with scripted approver personas and escalation."""

    requests: list[ApprovalRequest] = field(default_factory=list)
    escalation_chains: dict[str, list[str]] = field(default_factory=dict)

    def submit(self, request: ApprovalRequest) -> None:
        self.requests.append(request)

    def pending(self) -> list[ApprovalRequest]:
        return [r for r in self.requests if r.status == "pending"]

    def get(self, request_id: str) -> ApprovalRequest | None:
        for r in self.requests:
            if r.request_id == request_id:
                return r
        return None

    def decide(
        self,
        request_id: str,
        decision: Literal["approved", "denied"],
        approver: str,
        decided_at_s: int,
    ) -> bool:
        req = self.get(request_id)
        if req is None or req.status != "pending":
            return False
        req.status = decision
        req.approver = approver
        req.decided_at_s = decided_at_s
        return True

    def expire_stale(self, now_s: int) -> int:
        """Mark expired requests. Returns count of newly expired items."""
        count = 0
        for req in self.requests:
            if req.status == "pending" and req.expires_at_s > 0 and req.expires_at_s <= now_s:
                req.status = "expired"
                count += 1
        return count

    def auto_decide(
        self,
        persona: ApproverPersona,
        now_s: int,
        approver_name: str = "auto",
    ) -> int:
        """Apply a scripted approver persona to pending requests.

        - auto_approve: approves everything
        - auto_deny: denies everything
        - ask_human: does nothing (escalates)
        Returns count of decisions made.
        """
        if persona == "ask_human":
            return 0
        decision: Literal["approved", "denied"] = (
            "approved" if persona == "auto_approve" else "denied"
        )
        count = 0
        for req in list(self.pending()):
            self.decide(req.request_id, decision, approver_name, now_s)
            count += 1
        return count

    def escalation_metrics(self) -> dict[str, int]:
        """Summary metrics about the queue state."""
        return {
            "total": len(self.requests),
            "pending": len(self.pending()),
            "approved": sum(1 for r in self.requests if r.status == "approved"),
            "denied": sum(1 for r in self.requests if r.status == "denied"),
            "expired": sum(1 for r in self.requests if r.status == "expired"),
        }

    def pending_count(self) -> int:
        return len(self.pending())

    def total_count(self) -> int:
        return len(self.requests)

    def has_pending(self) -> bool:
        return any(r.status == "pending" for r in self.requests)

    def escalate(self, request_id: str, now_s: int) -> bool:
        """Escalate a request to the next approver in its chain.

        Returns True if escalation succeeded, False if no chain or at end.
        """
        req = self.get(request_id)
        if req is None or req.status != "pending":
            return False
        chain = self.escalation_chains.get(req.action, [])
        if not chain or req.escalation_level >= len(chain):
            return False
        next_approver = chain[req.escalation_level]
        req.escalation_level += 1
        req.approver = next_approver
        return True

    def expired_count(self) -> int:
        return sum(1 for r in self.requests if r.status == "expired")

    def escalated_count(self) -> int:
        return sum(1 for r in self.requests if r.escalation_level > 0)

    def average_decision_time(self) -> float:
        """Compute average time from creation to decision for decided requests."""
        decided = [r for r in self.requests if r.decided_at_s is not None and r.created_at_s > 0]
        if not decided:
            return 0.0
        total = sum(r.decided_at_s - r.created_at_s for r in decided)  # type: ignore[operator]
        return round(total / len(decided), 6)

    def add_escalation_chain(self, action: str, approvers: list[str]) -> None:
        """Register an escalation chain for an action type.

        Approvers are tried in order when requests for this action are
        escalated. Validates that the chain is non-empty and contains
        non-empty strings.
        """
        if not action.strip():
            raise ValueError("escalation chain action must be non-empty")
        if not approvers:
            raise ValueError("escalation chain must have at least one approver")
        if any(not isinstance(a, str) or not a.strip() for a in approvers):
            raise ValueError("escalation chain approvers must be non-empty strings")
        self.escalation_chains[action] = list(approvers)

    def validate_chains(self) -> list[str]:
        """Validate all registered escalation chains and return any problems."""
        problems: list[str] = []
        for action, chain in self.escalation_chains.items():
            if not action.strip():
                problems.append("escalation chain has empty action key")
            if not chain:
                problems.append(f"escalation chain for {action!r} is empty")
            for i, approver in enumerate(chain):
                if not isinstance(approver, str) or not approver.strip():
                    problems.append(
                        f"escalation chain for {action!r} has invalid approver at index {i}"
                    )
        return problems

    def chain_depth(self, action: str) -> int:
        """Return the length of the escalation chain for an action."""
        return len(self.escalation_chains.get(action, []))
