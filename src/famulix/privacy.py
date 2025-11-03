"""Privacy: PII detection, redaction, tier rules, and policy engine.

Handles PII detection via regex patterns (email, phone, card numbers with
Luhn check), reversible vs irreversible redaction, memory read/write/export
tiers, an immutable access log, and a declarative allow/deny/ask policy
engine with precedence and conflict diagnostics.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

RedactionMode = Literal["reversible", "irreversible"]
TierAction = Literal["allow", "deny", "ask"]
PolicyEffect = Literal["allow", "deny", "ask"]
PrivacyTier = Literal["public", "shared", "personal", "private"]

PRIVACY_TIER_LEVEL: dict[str, int] = {"public": 0, "shared": 1, "personal": 2, "private": 3}


# --- PII Detection ---------------------------------------------------------

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
ADDRESS_PATTERN = re.compile(
    r"\b\d{1,6}\s+(?:[A-Za-z0-9.'-]+\s+){0,5}"
    r"(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|court|ct)"
    r"\b(?:,?\s*(?:apt|suite|unit)\s*[A-Za-z0-9-]+)?",
    re.IGNORECASE,
)


def _luhn_check(number: str) -> bool:
    """Validate a card number using the Luhn algorithm."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


@dataclass
class PIIMatch:
    """A detected PII token with position and type."""

    pii_type: str
    start: int
    end: int
    text: str


def detect_pii(text: str) -> list[PIIMatch]:
    """Detect PII patterns in text.

    Returns matches sorted by position. Card numbers are validated via Luhn
    check to reduce false positives from arbitrary digit strings.
    """
    matches: list[PIIMatch] = []

    for m in EMAIL_PATTERN.finditer(text):
        matches.append(PIIMatch("email", m.start(), m.end(), m.group()))

    for m in PHONE_PATTERN.finditer(text):
        matches.append(PIIMatch("phone", m.start(), m.end(), m.group()))

    for m in ADDRESS_PATTERN.finditer(text):
        matches.append(PIIMatch("address", m.start(), m.end(), m.group()))

    for m in CARD_PATTERN.finditer(text):
        digits = re.sub(r"[ -]", "", m.group())
        if _luhn_check(digits):
            matches.append(PIIMatch("card", m.start(), m.end(), m.group()))

    matches.sort(key=lambda x: x.start)
    return matches


# --- Redaction -------------------------------------------------------------


def redact_text(
    text: str,
    mode: RedactionMode = "irreversible",
    *,
    salt: str = "",
) -> tuple[str, dict[str, str]]:
    """Redact PII from text.

    In irreversible mode, replaces each match with a type tag (e.g. [EMAIL]).
    In reversible mode, replaces with a hash-based token; returns a mapping
    from token to original value so the text can be restored.
    """
    if mode not in ("irreversible", "reversible"):
        raise ValueError(f"unsupported redaction mode: {mode}")
    matches = detect_pii(text)
    if not matches:
        return text, {}

    mapping: dict[str, str] = {}
    result_parts: list[str] = []
    last = 0
    counter = 0

    for match in matches:
        if match.start < last:
            continue
        result_parts.append(text[last : match.start])
        if mode == "irreversible":
            token = f"[{match.pii_type.upper()}]"
        else:
            counter += 1
            hashed = hashlib.sha256((salt + match.text + str(counter)).encode()).hexdigest()[:12]
            token = f"<PII:{match.pii_type}:{hashed}>"
            mapping[token] = match.text
        result_parts.append(token)
        last = match.end

    result_parts.append(text[last:])
    return "".join(result_parts), mapping


def restore_text(text: str, mapping: dict[str, str]) -> str:
    """Restore redacted text using a reversible-mode mapping."""
    result = text
    for token, original in mapping.items():
        result = result.replace(token, original)
    return result


# --- Tier Rules ------------------------------------------------------------


@dataclass(frozen=True)
class TierRule:
    """Access rule for a tier."""

    tier: str
    action: TierAction
    resource: str  # e.g. "memory:read", "memory:write", "memory:export"


@dataclass
class AccessLog:
    """Immutable append-only access log."""

    _entries: list[dict[str, object]] = field(default_factory=list, repr=False)

    @property
    def entries(self) -> tuple[Mapping[str, object], ...]:
        """Return immutable snapshots so callers cannot rewrite the audit trail."""
        return tuple(MappingProxyType(dict(entry)) for entry in self._entries)

    def record(
        self,
        *,
        actor: str,
        action: str,
        resource: str,
        result: str,
        timestamp_s: int,
    ) -> None:
        self._entries.append(
            {
                "actor": actor,
                "action": action,
                "resource": resource,
                "result": result,
                "timestamp_s": timestamp_s,
            }
        )

    def to_jsonl(self) -> str:
        """Serialize audit entries in stable JSONL order."""
        return "\n".join(
            json.dumps(dict(entry), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            for entry in self._entries
        )

    @classmethod
    def from_jsonl(cls, payload: str) -> AccessLog:
        log = cls()
        for number, line in enumerate(payload.splitlines(), start=1):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid access log JSON at line {number}") from exc
            required = {"actor", "action", "resource", "result", "timestamp_s"}
            if not isinstance(entry, dict) or set(entry) != required:
                raise ValueError(f"malformed access log entry at line {number}")
            if not all(isinstance(entry[key], str) for key in required - {"timestamp_s"}):
                raise ValueError(f"invalid access log text at line {number}")
            if type(entry["timestamp_s"]) is not int:
                raise ValueError(f"invalid access log timestamp at line {number}")
            log._entries.append(dict(entry))
        return log

    def count_by_result(self, result: str) -> int:
        return sum(1 for e in self.entries if e["result"] == result)

    def filter_by_actor(self, actor: str) -> list[dict[str, object]]:
        return [dict(e) for e in self._entries if e["actor"] == actor]

    def result_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self._entries:
            result = str(entry.get("result", "unknown"))
            counts[result] = counts.get(result, 0) + 1
        return counts

    def entry_count(self) -> int:
        return len(self._entries)


@dataclass(frozen=True)
class AccessDecision:
    """Audited result of a privacy-tier access request."""

    allowed: bool
    effect: PolicyEffect
    reason: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> AccessDecision:
        if set(data) != {"allowed", "effect", "reason"}:
            raise ValueError("malformed access decision")
        if (
            type(data["allowed"]) is not bool
            or data["effect"] not in {"allow", "deny", "ask"}
            or not isinstance(data["reason"], str)
        ):
            raise ValueError("invalid access decision fields")
        return cls(data["allowed"], data["effect"], data["reason"])

    def to_dict(self) -> dict[str, object]:
        return {"allowed": self.allowed, "effect": self.effect, "reason": self.reason}


class PrivacyGate:
    """Combine policy evaluation with monotonic privacy-tier enforcement."""

    def __init__(self, policy: PolicyEngine, audit: AccessLog | None = None) -> None:
        self.policy = policy
        self.audit = audit or AccessLog()

    def request(
        self,
        *,
        actor: str,
        action: str,
        resource: str,
        data_tier: PrivacyTier,
        clearance_tier: PrivacyTier,
        timestamp_s: int,
        destination_tier: PrivacyTier | None = None,
        approval_granted: bool = False,
    ) -> AccessDecision:
        """Check policy and clearance; exporting may never lower a tier."""
        if data_tier not in PRIVACY_TIER_LEVEL or clearance_tier not in PRIVACY_TIER_LEVEL:
            raise ValueError("unknown privacy tier")
        if destination_tier is not None and destination_tier not in PRIVACY_TIER_LEVEL:
            raise ValueError("unknown destination privacy tier")
        effect: PolicyEffect
        if (
            destination_tier is not None
            and PRIVACY_TIER_LEVEL[destination_tier] < PRIVACY_TIER_LEVEL[data_tier]
        ):
            effect, reason = "deny", "export would lower the data privacy tier"
        elif PRIVACY_TIER_LEVEL[clearance_tier] < PRIVACY_TIER_LEVEL[data_tier]:
            effect, reason = "deny", "actor clearance is below the data privacy tier"
        else:
            effect, rule_id = self.policy.evaluate(action=action, resource=resource, tier=data_tier)
            reason = f"matched policy {rule_id}" if rule_id else "no matching policy rule"
        allowed = effect == "allow" or (effect == "ask" and approval_granted)
        result = "allowed" if allowed else "approval_required" if effect == "ask" else "denied"
        self.audit.record(
            actor=actor,
            action=action,
            resource=resource,
            result=result,
            timestamp_s=timestamp_s,
        )
        return AccessDecision(allowed=allowed, effect=effect, reason=reason)


# --- Policy Engine ---------------------------------------------------------


@dataclass(frozen=True)
class PolicyRule:
    """A single policy rule with effect and match conditions."""

    id: str
    effect: PolicyEffect
    actions: set[str]
    resources: set[str]
    tiers: set[str]
    priority: int = 0


class PolicyEngine:
    """Evaluates policy rules and returns a decision.

    Rules are sorted by priority (highest first). The first matching rule's
    effect wins. If no rule matches, the default effect is 'deny'.
    """

    def __init__(self, default_effect: PolicyEffect = "deny") -> None:
        self._rules: list[PolicyRule] = []
        self.default_effect = default_effect

    def add_rule(self, rule: PolicyRule) -> None:
        if not rule.id.strip():
            raise ValueError("policy rule id must not be empty")
        if rule.effect not in {"allow", "deny", "ask"}:
            raise ValueError("policy rule effect is invalid")
        if type(rule.priority) is not int:
            raise ValueError("policy rule priority must be an integer")
        if any(
            not isinstance(value, str) or not value
            for values in (rule.actions, rule.resources, rule.tiers)
            for value in values
        ):
            raise ValueError("policy rule match values must be non-empty strings")
        if any(existing.id == rule.id for existing in self._rules):
            raise ValueError(f"duplicate policy rule id: {rule.id}")
        self._rules.append(rule)
        self._rules.sort(key=lambda r: (-r.priority, r.id))

    def evaluate(
        self,
        *,
        action: str,
        resource: str,
        tier: str,
    ) -> tuple[PolicyEffect, str | None]:
        """Evaluate a request. Returns (effect, matched_rule_id_or_None).

        Rules are checked in priority order (highest first). Empty match sets
        act as wildcards (match any value). Explicit "*" in a match set also
        acts as a wildcard for that dimension.
        """
        for rule in self._rules:
            if rule.actions and "*" not in rule.actions and action not in rule.actions:
                continue
            if rule.resources and "*" not in rule.resources and resource not in rule.resources:
                continue
            if rule.tiers and "*" not in rule.tiers and tier not in rule.tiers:
                continue
            return rule.effect, rule.id
        return self.default_effect, None

    def rule_count(self) -> int:
        return len(self._rules)

    def rule_ids(self) -> list[str]:
        return [rule.id for rule in self._rules]

    def check_conflicts(self) -> list[tuple[str, str]]:
        """Find pairs of rules that could conflict on the same request.

        Two rules conflict if they have the same priority, overlapping
        actions/resources/tiers, and different effects. Wildcards ("*" or
        empty sets) overlap with everything.
        """
        conflicts: list[tuple[str, str]] = []
        for i in range(len(self._rules)):
            for j in range(i + 1, len(self._rules)):
                a, b = self._rules[i], self._rules[j]
                if a.priority != b.priority:
                    continue
                if a.effect == b.effect:
                    continue
                # Check overlap
                if (
                    _sets_overlap(a.actions, b.actions)
                    and _sets_overlap(a.resources, b.resources)
                    and _sets_overlap(a.tiers, b.tiers)
                ):
                    conflicts.append((a.id, b.id))
        return conflicts


def _sets_overlap(left: set[str], right: set[str]) -> bool:
    """Empty policy dimensions or wildcards match every value."""
    if not left or not right:
        return True
    if "*" in left or "*" in right:
        return True
    return bool(left & right)


def _set_intersection(left: set[str], right: set[str]) -> set[str]:
    """Return the concrete overlap between two policy dimensions.

    Empty sets and wildcards ("*") overlap with everything, so the non-empty
    concrete set is returned when one side is wildcard/empty. Returns {"*"}
    when both sides are empty or wildcard.
    """
    if not left and not right:
        return {"*"}
    if not left or "*" in left:
        return right if right else {"*"}
    if not right or "*" in right:
        return left
    return left & right


@dataclass(frozen=True)
class ConflictDiagnostic:
    """Detailed report of a policy rule conflict."""

    rule_a_id: str
    rule_b_id: str
    rule_a_effect: str
    rule_b_effect: str
    priority: int
    overlapping_actions: frozenset[str]
    overlapping_resources: frozenset[str]
    overlapping_tiers: frozenset[str]

    def sample_request(self) -> dict[str, str] | None:
        """Return one concrete request both rules would match, or None."""
        if (
            not self.overlapping_actions
            or not self.overlapping_resources
            or not self.overlapping_tiers
        ):
            return None
        action = sorted(self.overlapping_actions)[0]
        resource = sorted(self.overlapping_resources)[0]
        tier = sorted(self.overlapping_tiers)[0]
        if action == "*" or resource == "*" or tier == "*":
            return None
        return {"action": action, "resource": resource, "tier": tier}

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_a_id": self.rule_a_id,
            "rule_b_id": self.rule_b_id,
            "rule_a_effect": self.rule_a_effect,
            "rule_b_effect": self.rule_b_effect,
            "priority": self.priority,
            "overlapping_actions": sorted(self.overlapping_actions),
            "overlapping_resources": sorted(self.overlapping_resources),
            "overlapping_tiers": sorted(self.overlapping_tiers),
        }


def diagnose_conflicts(engine: PolicyEngine) -> list[ConflictDiagnostic]:
    """Produce detailed diagnostics for every conflicting rule pair.

    The diagnostics include the concrete overlap sets so administrators can
    see which requests would produce ambiguous decisions. The sample_request
    method returns one such request for reproduction.
    """
    diagnostics: list[ConflictDiagnostic] = []
    rules = engine._rules  # noqa: SLF001
    for i in range(len(rules)):
        for j in range(i + 1, len(rules)):
            a, b = rules[i], rules[j]
            if a.priority != b.priority or a.effect == b.effect:
                continue
            actions = _set_intersection(a.actions, b.actions)
            resources = _set_intersection(a.resources, b.resources)
            tiers = _set_intersection(a.tiers, b.tiers)
            if actions and resources and tiers:
                diagnostics.append(
                    ConflictDiagnostic(
                        rule_a_id=a.id,
                        rule_b_id=b.id,
                        rule_a_effect=a.effect,
                        rule_b_effect=b.effect,
                        priority=a.priority,
                        overlapping_actions=frozenset(actions),
                        overlapping_resources=frozenset(resources),
                        overlapping_tiers=frozenset(tiers),
                    )
                )
    return diagnostics
