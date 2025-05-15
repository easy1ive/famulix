"""Tests for privacy: PII detection, redaction, policy engine."""

from __future__ import annotations

import pytest

from famulix.privacy import (
    AccessLog,
    PIIMatch,
    PolicyEngine,
    PolicyRule,
    PrivacyGate,
    detect_pii,
    redact_text,
    restore_text,
)


def test_detect_email() -> None:
    matches = detect_pii("Contact me at alice@example.com please")
    assert len(matches) >= 1
    assert any(m.pii_type == "email" for m in matches)
    assert "alice@example.com" in [m.text for m in matches]


def test_detect_phone() -> None:
    matches = detect_pii("Call me at 555-123-4567")
    assert any(m.pii_type == "phone" for m in matches)


def test_detect_street_address_and_redact_both_directions() -> None:
    text = "Send the letter to 123 Main Street, Apt 4B tomorrow."
    matches = detect_pii(text)
    address = next(match for match in matches if match.pii_type == "address")
    assert address.text == "123 Main Street, Apt 4B"

    redacted, mapping = redact_text(text, mode="reversible", salt="fixture")
    assert address.text not in redacted
    assert restore_text(redacted, mapping) == text


def test_address_detector_ignores_unqualified_street_names() -> None:
    assert not any(
        match.pii_type == "address" for match in detect_pii("Meet me on Main Street after work.")
    )


def test_detect_card_valid_luhn() -> None:
    # Standard Visa test number (Luhn-valid)
    matches = detect_pii("Card: 4111 1111 1111 1111")
    assert any(m.pii_type == "card" for m in matches)


def test_detect_card_rejects_invalid_luhn() -> None:
    # Not a valid card number
    matches = detect_pii("Number: 1234 5678 9012 3456")
    assert not any(m.pii_type == "card" for m in matches)


def test_detect_pii_sorted_by_position() -> None:
    matches = detect_pii("alice@example.com and 555-123-4567")
    starts = [m.start for m in matches]
    assert starts == sorted(starts)


def test_detect_pii_clean_text() -> None:
    matches = detect_pii("This is a perfectly safe sentence with no PII.")
    assert matches == []


def test_irreversible_redaction() -> None:
    text = "Email alice@example.com is private."
    redacted, mapping = redact_text(text, mode="irreversible")
    assert "alice@example.com" not in redacted
    assert "[EMAIL]" in redacted
    assert mapping == {}


def test_redaction_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="unsupported redaction mode"):
        redact_text("alice@example.com", mode="unknown")  # type: ignore[arg-type]


def test_reversible_redaction_round_trip() -> None:
    text = "Call alice@example.com or 555-123-4567."
    redacted, mapping = redact_text(text, mode="reversible", salt="test")
    assert "alice@example.com" not in redacted
    assert "555-123-4567" not in redacted
    assert len(mapping) >= 2
    restored = restore_text(redacted, mapping)
    assert restored == text


def test_reversible_redaction_different_salts() -> None:
    text = "a@b.com"
    r1, m1 = redact_text(text, mode="reversible", salt="salt1")
    r2, m2 = redact_text(text, mode="reversible", salt="salt2")
    # Different salts produce different tokens
    assert list(m1.keys()) != list(m2.keys())


def test_access_log_append_only() -> None:
    log = AccessLog()
    log.record(actor="user1", action="read", resource="mem/1", result="allowed", timestamp_s=100)
    log.record(actor="user2", action="export", resource="mem/2", result="denied", timestamp_s=200)
    assert len(log.entries) == 2
    assert log.count_by_result("allowed") == 1
    assert log.count_by_result("denied") == 1
    assert len(log.filter_by_actor("user1")) == 1


def test_access_log_exposes_read_only_snapshots() -> None:
    log = AccessLog()
    log.record(actor="u", action="read", resource="memory/1", result="allowed", timestamp_s=5)
    with pytest.raises(TypeError):
        log.entries[0]["result"] = "denied"  # type: ignore[index]
    copied = log.filter_by_actor("u")
    copied[0]["result"] = "denied"
    assert log.entries[0]["result"] == "allowed"


def test_privacy_gate_blocks_lower_tier_export_even_when_policy_allows() -> None:
    policy = PolicyEngine(default_effect="allow")
    audit = AccessLog()
    gate = PrivacyGate(policy, audit)

    decision = gate.request(
        actor="local-user",
        action="export",
        resource="memory/secret",
        data_tier="private",
        clearance_tier="private",
        destination_tier="public",
        timestamp_s=10,
    )

    assert not decision.allowed
    assert decision.effect == "deny"
    assert "lower" in decision.reason
    assert audit.entries[-1]["result"] == "denied"


def test_privacy_gate_requires_clearance_and_records_approval_state() -> None:
    policy = PolicyEngine(default_effect="ask")
    audit = AccessLog()
    gate = PrivacyGate(policy, audit)
    denied = gate.request(
        actor="guest",
        action="read",
        resource="memory/one",
        data_tier="personal",
        clearance_tier="shared",
        timestamp_s=1,
    )
    asked = gate.request(
        actor="owner",
        action="read",
        resource="memory/one",
        data_tier="personal",
        clearance_tier="private",
        timestamp_s=2,
    )
    approved = gate.request(
        actor="owner",
        action="read",
        resource="memory/one",
        data_tier="personal",
        clearance_tier="private",
        timestamp_s=3,
        approval_granted=True,
    )

    assert denied.effect == "deny" and not denied.allowed
    assert asked.effect == "ask" and not asked.allowed
    assert approved.effect == "ask" and approved.allowed
    assert [row["result"] for row in audit.entries] == [
        "denied",
        "approval_required",
        "allowed",
    ]


def test_policy_engine_default_deny() -> None:
    pe = PolicyEngine(default_effect="deny")
    effect, rule_id = pe.evaluate(action="read", resource="mem/1", tier="hot")
    assert effect == "deny"
    assert rule_id is None


def test_policy_engine_allow_rule() -> None:
    pe = PolicyEngine()
    pe.add_rule(
        PolicyRule(
            id="r1",
            effect="allow",
            actions={"read"},
            resources={"mem/1"},
            tiers={"hot"},
            priority=10,
        )
    )
    effect, rule_id = pe.evaluate(action="read", resource="mem/1", tier="hot")
    assert effect == "allow"
    assert rule_id == "r1"


def test_policy_engine_priority_order() -> None:
    pe = PolicyEngine()
    pe.add_rule(
        PolicyRule(
            id="low_priority_deny",
            effect="deny",
            actions={"read"},
            resources={"mem/1"},
            tiers={"hot"},
            priority=1,
        )
    )
    pe.add_rule(
        PolicyRule(
            id="high_priority_allow",
            effect="allow",
            actions={"read"},
            resources={"mem/1"},
            tiers={"hot"},
            priority=100,
        )
    )
    effect, rule_id = pe.evaluate(action="read", resource="mem/1", tier="hot")
    assert effect == "allow"
    assert rule_id == "high_priority_allow"


def test_policy_engine_no_match_on_different_tier() -> None:
    pe = PolicyEngine()
    pe.add_rule(
        PolicyRule(
            id="r1",
            effect="allow",
            actions={"read"},
            resources={"mem/1"},
            tiers={"hot"},
            priority=10,
        )
    )
    effect, _ = pe.evaluate(action="read", resource="mem/1", tier="cold")
    assert effect == "deny"


def test_policy_conflicts_detected() -> None:
    pe = PolicyEngine()
    pe.add_rule(
        PolicyRule(
            id="r1",
            effect="allow",
            actions={"read"},
            resources={"mem/x"},
            tiers={"hot"},
            priority=5,
        )
    )
    pe.add_rule(
        PolicyRule(
            id="r2",
            effect="deny",
            actions={"read"},
            resources={"mem/x"},
            tiers={"hot"},
            priority=5,
        )
    )
    conflicts = pe.check_conflicts()
    assert len(conflicts) == 1
    assert set(conflicts[0]) == {"r1", "r2"}


def test_policy_no_conflicts_different_priority() -> None:
    pe = PolicyEngine()
    pe.add_rule(
        PolicyRule(
            id="r1",
            effect="allow",
            actions={"read"},
            resources={"mem/x"},
            tiers={"hot"},
            priority=1,
        )
    )
    pe.add_rule(
        PolicyRule(
            id="r2",
            effect="deny",
            actions={"read"},
            resources={"mem/x"},
            tiers={"hot"},
            priority=2,
        )
    )
    assert pe.check_conflicts() == []


def test_policy_conflict_detection_treats_empty_scope_as_wildcard() -> None:
    pe = PolicyEngine()
    pe.add_rule(
        PolicyRule(
            id="global-allow",
            effect="allow",
            actions=set(),
            resources=set(),
            tiers=set(),
            priority=4,
        )
    )
    pe.add_rule(
        PolicyRule(
            id="private-deny",
            effect="deny",
            actions={"export"},
            resources={"memory/private"},
            tiers={"private"},
            priority=4,
        )
    )

    assert pe.check_conflicts() == [("global-allow", "private-deny")]


def test_piimatch_dataclass() -> None:
    m = PIIMatch("email", 0, 5, "a@b.co")
    assert m.pii_type == "email"
    assert m.start == 0
    assert m.end == 5


def test_access_log_jsonl_roundtrip_is_stable() -> None:
    from famulix.privacy import AccessLog

    log = AccessLog()
    log.record(actor="app", action="read", resource="memory", result="allowed", timestamp_s=3)
    payload = log.to_jsonl()
    assert AccessLog.from_jsonl(payload).to_jsonl() == payload


def test_access_decision_roundtrip_rejects_shape_drift() -> None:
    import pytest

    from famulix.privacy import AccessDecision

    decision = AccessDecision(True, "allow", "matched")
    assert AccessDecision.from_dict(decision.to_dict()) == decision
    with pytest.raises(ValueError, match="malformed"):
        AccessDecision.from_dict({"allowed": True})


def test_policy_engine_rejects_duplicate_and_empty_rule_ids() -> None:
    import pytest

    from famulix.privacy import PolicyEngine, PolicyRule

    engine = PolicyEngine()
    rule = PolicyRule("read", "allow", {"read"}, {"memory"}, {"personal"})
    engine.add_rule(rule)
    with pytest.raises(ValueError, match="duplicate"):
        engine.add_rule(rule)
    with pytest.raises(ValueError, match="id"):
        engine.add_rule(PolicyRule("", "deny", set(), set(), set()))
