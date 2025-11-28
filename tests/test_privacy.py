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


def test_policy_precedence_is_independent_of_insertion_order() -> None:
    from famulix.privacy import PolicyEngine, PolicyRule

    engine = PolicyEngine()
    engine.add_rule(PolicyRule("z-deny", "deny", {"read"}, {"memory"}, {"personal"}, 4))
    engine.add_rule(PolicyRule("a-allow", "allow", {"read"}, {"memory"}, {"personal"}, 4))
    assert engine.evaluate(action="read", resource="memory", tier="personal") == (
        "allow",
        "a-allow",
    )


def test_redaction_does_not_duplicate_overlapping_matches() -> None:
    from famulix.privacy import redact_text

    text, mapping = redact_text("mail me at 12345678901@example.com")
    assert text.count("[EMAIL]") == 1
    assert len(mapping) == 0


def test_access_log_decoder_rejects_unknown_fields() -> None:
    import pytest

    from famulix.privacy import AccessLog

    with pytest.raises(ValueError, match="malformed"):
        AccessLog.from_jsonl(
            '{"actor":"a","action":"r","resource":"m","result":"allowed","timestamp_s":1,"extra":0}'
        )


def test_access_log_result_summary_counts_correctly() -> None:
    from famulix.privacy import AccessLog

    log = AccessLog()
    log.record(actor="user1", action="read", resource="mem1", result="allowed", timestamp_s=100)
    log.record(actor="user1", action="read", resource="mem2", result="allowed", timestamp_s=200)
    log.record(actor="user2", action="export", resource="mem1", result="denied", timestamp_s=300)
    summary = log.result_summary()
    assert summary["allowed"] == 2
    assert summary["denied"] == 1
    assert sum(summary.values()) == log.entry_count()


def test_access_log_entry_count_matches_records() -> None:
    from famulix.privacy import AccessLog

    log = AccessLog()
    assert log.entry_count() == 0
    log.record(actor="a", action="r", resource="m", result="allowed", timestamp_s=1)
    assert log.entry_count() == 1
    log.record(actor="a", action="w", resource="m", result="denied", timestamp_s=2)
    assert log.entry_count() == 2


def test_access_decision_declares_its_three_fields_once() -> None:
    """The decision record must not carry a duplicated field block."""
    from dataclasses import fields

    from famulix.privacy import AccessDecision

    assert [f.name for f in fields(AccessDecision)] == ["allowed", "effect", "reason"]
    assert (AccessDecision.__doc__ or "").startswith("Audited result")
    decision = AccessDecision(allowed=False, effect="deny", reason="tier too low")
    assert AccessDecision.from_dict(decision.to_dict()) == decision


def test_access_decision_from_dict_rejects_extra_and_missing_keys() -> None:
    import pytest

    from famulix.privacy import AccessDecision

    base = {"allowed": True, "effect": "allow", "reason": "ok"}
    assert AccessDecision.from_dict(base).allowed is True
    with pytest.raises(ValueError):
        AccessDecision.from_dict({**base, "extra": 1})
    with pytest.raises(ValueError):
        AccessDecision.from_dict({"allowed": True, "effect": "allow"})
    with pytest.raises(ValueError):
        AccessDecision.from_dict({**base, "effect": "maybe"})
    with pytest.raises(ValueError):
        AccessDecision.from_dict({**base, "allowed": "yes"})


def test_policy_wildcard_star_matches_any_action() -> None:
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(id="r1", effect="allow", actions={"*"}, resources={"mem:read"}, tiers=set())
    )
    effect, rule_id = engine.evaluate(action="read", resource="mem:read", tier="public")
    assert effect == "allow"
    assert rule_id == "r1"


def test_policy_wildcard_star_matches_any_resource() -> None:
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(id="r1", effect="allow", actions={"read"}, resources={"*"}, tiers=set())
    )
    effect, rule_id = engine.evaluate(action="read", resource="anything", tier="public")
    assert effect == "allow"
    assert rule_id == "r1"


def test_policy_wildcard_empty_set_matches_all() -> None:
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(id="r1", effect="allow", actions=set(), resources=set(), tiers=set())
    )
    effect, rule_id = engine.evaluate(action="write", resource="mem:write", tier="private")
    assert effect == "allow"
    assert rule_id == "r1"


def test_policy_priority_overrides_wildcard() -> None:
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="allow_all", effect="allow", actions=set(), resources=set(), tiers=set(), priority=0
        )
    )
    engine.add_rule(
        PolicyRule(
            id="deny_write",
            effect="deny",
            actions={"write"},
            resources=set(),
            tiers=set(),
            priority=10,
        )
    )
    effect, rule_id = engine.evaluate(action="write", resource="mem:write", tier="public")
    assert effect == "deny"
    assert rule_id == "deny_write"
    effect2, rule_id2 = engine.evaluate(action="read", resource="mem:read", tier="public")
    assert effect2 == "allow"
    assert rule_id2 == "allow_all"


def test_policy_conflict_detection_with_wildcards() -> None:
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="r1", effect="allow", actions={"*"}, resources={"mem:read"}, tiers=set(), priority=5
        )
    )
    engine.add_rule(
        PolicyRule(
            id="r2", effect="deny", actions={"read"}, resources={"*"}, tiers=set(), priority=5
        )
    )
    conflicts = engine.check_conflicts()
    assert len(conflicts) == 1
    assert set(conflicts[0]) == {"r1", "r2"}


def test_policy_engine_rule_helpers() -> None:
    engine = PolicyEngine()
    assert engine.rule_count() == 0
    assert engine.rule_ids() == []
    engine.add_rule(PolicyRule(id="a", effect="allow", actions=set(), resources=set(), tiers=set()))
    engine.add_rule(
        PolicyRule(id="b", effect="deny", actions={"write"}, resources=set(), tiers=set())
    )
    assert engine.rule_count() == 2
    assert set(engine.rule_ids()) == {"a", "b"}


def test_redaction_reversible_roundtrip_preserves_all_pii() -> None:
    text = "Email: alice@example.com, Phone: 555-123-4567, Card: 4111 1111 1111 1111"
    redacted, mapping = redact_text(text, mode="reversible", salt="test")
    restored = restore_text(redacted, mapping)
    assert restored == text
    assert "alice@example.com" in restored
    assert "555-123-4567" in restored
    assert "4111 1111 1111 1111" in restored


def test_redaction_irreversible_cannot_be_restored() -> None:
    text = "Contact alice@example.com for details"
    redacted, mapping = redact_text(text, mode="irreversible")
    assert mapping == {}
    assert "alice@example.com" not in redacted
    assert "[EMAIL]" in redacted
    restored = restore_text(redacted, mapping)
    assert restored == redacted
    assert "alice@example.com" not in restored


def test_redaction_reversible_with_multiple_same_type_pii() -> None:
    text = "Send to alice@example.com and bob@example.com"
    redacted, mapping = redact_text(text, mode="reversible", salt="multi")
    assert len(mapping) == 2
    restored = restore_text(redacted, mapping)
    assert restored == text
    assert "alice@example.com" in restored
    assert "bob@example.com" in restored


def test_redaction_deterministic_with_same_salt() -> None:
    text = "Email: test@example.com"
    redacted1, mapping1 = redact_text(text, mode="reversible", salt="fixed")
    redacted2, mapping2 = redact_text(text, mode="reversible", salt="fixed")
    assert redacted1 == redacted2
    assert mapping1 == mapping2


def test_redaction_different_salt_produces_different_tokens() -> None:
    text = "Email: test@example.com"
    redacted1, mapping1 = redact_text(text, mode="reversible", salt="salt1")
    redacted2, mapping2 = redact_text(text, mode="reversible", salt="salt2")
    assert redacted1 != redacted2
    assert list(mapping1.values()) == list(mapping2.values())
    assert list(mapping1.keys()) != list(mapping2.keys())


def test_access_log_records_entries_in_order() -> None:
    from famulix.privacy import AccessLog

    log = AccessLog()
    log.record(actor="user1", action="read", resource="mem:1", result="allowed", timestamp_s=100)
    log.record(actor="user2", action="write", resource="mem:2", result="denied", timestamp_s=200)
    assert log.entry_count() == 2
    entries = log.entries
    assert entries[0]["actor"] == "user1"
    assert entries[1]["actor"] == "user2"


def test_access_log_immutable_entries() -> None:
    from famulix.privacy import AccessLog

    log = AccessLog()
    log.record(actor="user", action="read", resource="mem:1", result="allowed", timestamp_s=100)
    entries = log.entries
    assert isinstance(entries, tuple)


def test_access_log_filter_by_actor() -> None:
    from famulix.privacy import AccessLog

    log = AccessLog()
    log.record(actor="alice", action="read", resource="mem:1", result="allowed", timestamp_s=100)
    log.record(actor="bob", action="write", resource="mem:2", result="denied", timestamp_s=200)
    log.record(actor="alice", action="read", resource="mem:3", result="allowed", timestamp_s=300)
    alice_entries = log.filter_by_actor("alice")
    assert len(alice_entries) == 2
    assert all(e["actor"] == "alice" for e in alice_entries)


def test_access_log_result_summary() -> None:
    from famulix.privacy import AccessLog

    log = AccessLog()
    log.record(actor="u1", action="read", resource="r1", result="allowed", timestamp_s=100)
    log.record(actor="u2", action="write", resource="r2", result="denied", timestamp_s=200)
    log.record(actor="u3", action="read", resource="r3", result="allowed", timestamp_s=300)
    summary = log.result_summary()
    assert summary["allowed"] == 2
    assert summary["denied"] == 1


def test_privacy_gate_blocks_lower_clearance() -> None:
    from famulix.privacy import AccessLog, PolicyEngine, PrivacyGate

    engine = PolicyEngine()
    gate = PrivacyGate(engine, audit=AccessLog())
    decision = gate.request(
        actor="user",
        action="read",
        resource="mem:1",
        data_tier="private",
        clearance_tier="shared",
        timestamp_s=100,
    )
    assert not decision.allowed
    assert "clearance" in decision.reason.lower()


def test_privacy_gate_allows_matching_clearance() -> None:
    from famulix.privacy import AccessLog, PolicyEngine, PolicyRule, PrivacyGate

    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="allow_read",
            effect="allow",
            actions={"read"},
            resources={"mem:1"},
            tiers={"personal"},
        )
    )
    gate = PrivacyGate(engine, audit=AccessLog())
    decision = gate.request(
        actor="user",
        action="read",
        resource="mem:1",
        data_tier="personal",
        clearance_tier="personal",
        timestamp_s=100,
    )
    assert decision.allowed


def test_diagnose_conflicts_reports_overlap() -> None:
    from famulix.privacy import PolicyEngine, PolicyRule, diagnose_conflicts

    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="allow-read",
            effect="allow",
            actions={"read"},
            resources={"notes"},
            tiers={"personal"},
            priority=10,
        )
    )
    engine.add_rule(
        PolicyRule(
            id="deny-read",
            effect="deny",
            actions={"read"},
            resources={"notes"},
            tiers={"personal"},
            priority=10,
        )
    )
    diagnostics = diagnose_conflicts(engine)
    assert len(diagnostics) == 1
    diag = diagnostics[0]
    assert diag.rule_a_id == "allow-read"
    assert diag.rule_b_id == "deny-read"
    assert diag.overlapping_actions == frozenset({"read"})
    sample = diag.sample_request()
    assert sample == {"action": "read", "resource": "notes", "tier": "personal"}


def test_diagnose_conflicts_handles_wildcards() -> None:
    from famulix.privacy import PolicyEngine, PolicyRule, diagnose_conflicts

    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="allow-all",
            effect="allow",
            actions=set(),
            resources=set(),
            tiers=set(),
            priority=5,
        )
    )
    engine.add_rule(
        PolicyRule(
            id="deny-write",
            effect="deny",
            actions={"write"},
            resources={"notes"},
            tiers={"private"},
            priority=5,
        )
    )
    diagnostics = diagnose_conflicts(engine)
    assert len(diagnostics) == 1
    diag = diagnostics[0]
    assert "write" in diag.overlapping_actions
    assert "notes" in diag.overlapping_resources
    assert "private" in diag.overlapping_tiers


def test_diagnose_conflicts_skips_different_priorities() -> None:
    from famulix.privacy import PolicyEngine, PolicyRule, diagnose_conflicts

    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="high", effect="allow", actions={"read"}, resources={"*"}, tiers={"*"}, priority=10
        )
    )
    engine.add_rule(
        PolicyRule(
            id="low", effect="deny", actions={"read"}, resources={"*"}, tiers={"*"}, priority=5
        )
    )
    assert diagnose_conflicts(engine) == []


def test_conflict_diagnostic_to_dict() -> None:
    from famulix.privacy import PolicyEngine, PolicyRule, diagnose_conflicts

    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="a",
            effect="allow",
            actions={"read"},
            resources={"notes"},
            tiers={"personal"},
            priority=1,
        )
    )
    engine.add_rule(
        PolicyRule(
            id="b",
            effect="deny",
            actions={"read"},
            resources={"notes"},
            tiers={"personal"},
            priority=1,
        )
    )
    diagnostics = diagnose_conflicts(engine)
    assert len(diagnostics) == 1
    d = diagnostics[0].to_dict()
    assert d["rule_a_id"] == "a"
    assert d["overlapping_actions"] == ["read"]


def test_simulate_policy_requests_basic() -> None:
    from famulix.privacy import PolicyEngine, PolicyRule, simulate_policy_requests

    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="allow_read",
            effect="allow",
            actions={"read"},
            resources={"notes"},
            tiers={"public"},
            priority=1,
        )
    )

    requests = [
        {"action": "read", "resource": "notes", "tier": "public", "actor": "user1"},
        {"action": "write", "resource": "notes", "tier": "public", "actor": "user1"},
    ]

    result = simulate_policy_requests(engine, requests)
    assert result["total_requests"] == 2
    assert result["allow_count"] == 1
    assert result["deny_count"] == 1
    assert len(result["decisions"]) == 2
    assert result["decisions"][0]["effect"] == "allow"
    assert result["decisions"][1]["effect"] == "deny"


def test_simulate_policy_requests_with_audit() -> None:
    from famulix.privacy import AccessLog, PolicyEngine, PolicyRule, simulate_policy_requests

    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="allow_all",
            effect="allow",
            actions={"*"},
            resources={"*"},
            tiers={"*"},
            priority=1,
        )
    )
    audit = AccessLog()

    requests = [
        {"action": "read", "resource": "notes", "tier": "public", "actor": "alice"},
        {"action": "write", "resource": "calendar", "tier": "personal", "actor": "bob"},
    ]

    result = simulate_policy_requests(engine, requests, audit=audit)
    assert result["total_requests"] == 2
    assert result["allow_count"] == 2
    assert audit.entry_count() == 2


def test_simulate_policy_requests_mixed_effects() -> None:
    from famulix.privacy import PolicyEngine, PolicyRule, simulate_policy_requests

    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="allow_read",
            effect="allow",
            actions={"read"},
            resources={"*"},
            tiers={"*"},
            priority=1,
        )
    )
    engine.add_rule(
        PolicyRule(
            id="ask_write",
            effect="ask",
            actions={"write"},
            resources={"*"},
            tiers={"*"},
            priority=1,
        )
    )

    requests = [
        {"action": "read", "resource": "notes", "tier": "public", "actor": "user1"},
        {"action": "write", "resource": "notes", "tier": "public", "actor": "user1"},
        {"action": "delete", "resource": "notes", "tier": "public", "actor": "user1"},
    ]

    result = simulate_policy_requests(engine, requests)
    assert result["total_requests"] == 3
    assert result["allow_count"] == 1
    assert result["ask_count"] == 1
    assert result["deny_count"] == 1
