"""Privacy: PII detection, redaction, tier rules, and policy engine.

Handles PII detection via regex patterns (email, phone, card numbers with
Luhn check), reversible vs irreversible redaction, memory read/write/export
tiers, an immutable access log, and a declarative allow/deny/ask policy
engine with precedence and conflict diagnostics.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Literal

RedactionMode = Literal["reversible", "irreversible"]
TierAction = Literal["allow", "deny", "ask"]
PolicyEffect = Literal["allow", "deny", "ask"]


# --- PII Detection ---------------------------------------------------------

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


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
    matches = detect_pii(text)
    if not matches:
        return text, {}

    mapping: dict[str, str] = {}
    result_parts: list[str] = []
    last = 0
    counter = 0

    for match in matches:
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

    entries: list[dict[str, object]] = field(default_factory=list)

    def record(
        self,
        *,
        actor: str,
        action: str,
        resource: str,
        result: str,
        timestamp_s: int,
    ) -> None:
        self.entries.append(
            {
                "actor": actor,
                "action": action,
                "resource": resource,
                "result": result,
                "timestamp_s": timestamp_s,
            }
        )

    def count_by_result(self, result: str) -> int:
        return sum(1 for e in self.entries if e["result"] == result)

    def filter_by_actor(self, actor: str) -> list[dict[str, object]]:
        return [e for e in self.entries if e["actor"] == actor]


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
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate(
        self,
        *,
        action: str,
        resource: str,
        tier: str,
    ) -> tuple[PolicyEffect, str | None]:
        """Evaluate a request. Returns (effect, matched_rule_id_or_None)."""
        for rule in self._rules:
            if rule.actions and action not in rule.actions:
                continue
            if rule.resources and resource not in rule.resources:
                continue
            if rule.tiers and tier not in rule.tiers:
                continue
            return rule.effect, rule.id
        return self.default_effect, None

    def check_conflicts(self) -> list[tuple[str, str]]:
        """Find pairs of rules that could conflict on the same request.

        Two rules conflict if they have the same priority, overlapping
        actions/resources/tiers, and different effects.
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
                if a.actions & b.actions and a.resources & b.resources and a.tiers & b.tiers:
                    conflicts.append((a.id, b.id))
        return conflicts
