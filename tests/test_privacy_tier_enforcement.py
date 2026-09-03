"""Privacy tier enforcement: data never leaks across tier boundaries."""

from famulix.privacy import PolicyEngine, PolicyRule


def test_allow_rule_grants_access():
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="allow_hot",
            effect="allow",
            priority=1,
            actions={"read"},
            resources={"*"},
            tiers={"hot"},
        )
    )
    effect, rule_id = engine.evaluate(action="read", resource="test", tier="hot")
    assert effect == "allow"
    assert rule_id == "allow_hot"


def test_no_matching_rule_means_deny():
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="allow_hot",
            effect="allow",
            priority=1,
            actions={"read"},
            resources={"*"},
            tiers={"hot"},
        )
    )
    effect, rule_id = engine.evaluate(action="read", resource="test", tier="cold")
    assert effect == "deny"
    assert rule_id is None


def test_deny_rule_blocks_access():
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="deny_all",
            effect="deny",
            priority=1,
            actions={"read"},
            resources={"*"},
            tiers={"*"},
        )
    )
    effect, _ = engine.evaluate(action="read", resource="test", tier="hot")
    assert effect == "deny"


def test_higher_priority_wins():
    engine = PolicyEngine()
    engine.add_rule(
        PolicyRule(
            id="allow_low",
            effect="allow",
            priority=1,
            actions={"read"},
            resources={"*"},
            tiers={"*"},
        )
    )
    engine.add_rule(
        PolicyRule(
            id="deny_high",
            effect="deny",
            priority=10,
            actions={"read"},
            resources={"*"},
            tiers={"*"},
        )
    )
    effect, rule_id = engine.evaluate(action="read", resource="test", tier="hot")
    assert effect == "deny"
    assert rule_id == "deny_high"


def test_tier_leak_matrix():
    """Each tier's policy only grants access to that tier's data."""
    tiers = ["hot", "warm", "cold", "archive"]
    for allowed_tier in tiers:
        for queried_tier in tiers:
            engine = PolicyEngine()
            engine.add_rule(
                PolicyRule(
                    id=f"allow_{allowed_tier}",
                    effect="allow",
                    priority=1,
                    actions={"read"},
                    resources={"*"},
                    tiers={allowed_tier},
                )
            )
            effect, _ = engine.evaluate(action="read", resource="data", tier=queried_tier)
            if allowed_tier != queried_tier:
                assert effect == "deny", (
                    f"tier leak: {allowed_tier}-only policy allowed {queried_tier} access"
                )
            else:
                assert effect == "allow"
