"""Tests for policy engine conflict detection and diagnostics."""

from famulix.privacy import PolicyEngine, PolicyRule, diagnose_conflicts


def test_no_conflicts_with_different_priorities():
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="r1",
            effect="allow",
            priority=1,
            actions={"read"},
            resources={"*"},
            tiers={"*"},
        )
    )
    engine.add_rule(
        PolicyRule(
            id="r2",
            effect="deny",
            priority=2,
            actions={"read"},
            resources={"*"},
            tiers={"*"},
        )
    )
    conflicts = engine.check_conflicts()
    assert len(conflicts) == 0


def test_conflict_same_priority_different_effect():
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="r1",
            effect="allow",
            priority=1,
            actions={"read"},
            resources={"memories"},
            tiers={"hot"},
        )
    )
    engine.add_rule(
        PolicyRule(
            id="r2",
            effect="deny",
            priority=1,
            actions={"read"},
            resources={"memories"},
            tiers={"hot"},
        )
    )
    conflicts = engine.check_conflicts()
    assert len(conflicts) >= 1


def test_no_conflict_same_priority_same_effect():
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="r1",
            effect="allow",
            priority=1,
            actions={"read"},
            resources={"memories"},
            tiers={"hot"},
        )
    )
    engine.add_rule(
        PolicyRule(
            id="r2",
            effect="allow",
            priority=1,
            actions={"write"},
            resources={"memories"},
            tiers={"hot"},
        )
    )
    conflicts = engine.check_conflicts()
    assert len(conflicts) == 0


def test_diagnose_conflicts_returns_diagnostics():
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="r1",
            effect="allow",
            priority=1,
            actions={"read", "write"},
            resources={"memories"},
            tiers={"hot"},
        )
    )
    engine.add_rule(
        PolicyRule(
            id="r2",
            effect="deny",
            priority=1,
            actions={"read"},
            resources={"memories"},
            tiers={"hot"},
        )
    )
    diagnostics = diagnose_conflicts(engine)
    assert len(diagnostics) >= 1


def test_diagnose_conflicts_no_conflicts():
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="r1",
            effect="allow",
            priority=1,
            actions={"read"},
            resources={"*"},
            tiers={"*"},
        )
    )
    diagnostics = diagnose_conflicts(engine)
    assert diagnostics == []
