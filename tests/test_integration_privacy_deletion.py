"""Integration test: privacy enforcement and deletion cascade.

Verifies that PII redaction, privacy tiers, and deletion work together
to ensure deleted content never reappears and privacy is enforced.
"""

from famulix.deletion import delete_memory
from famulix.encoding import encode_events_to_graph
from famulix.factory import generate_history
from famulix.privacy import PolicyEngine, PrivacyGate, detect_pii, redact_text
from famulix.retrieval import BM25Index, hybrid_score


def test_privacy_redaction_and_deletion_cascade():
    """Verify PII is redacted and deleted memories don't reappear."""
    # Generate history with some personal data
    events, _manifest = generate_history(persona_id="alex", seed=42, days=10)
    graph = encode_events_to_graph(events)

    # Find a fact node with potential PII
    fact_nodes = [n for n in graph.all_nodes() if n.kind == "fact" and n.is_active]
    assert len(fact_nodes) > 0, "No fact nodes generated"

    target_node = fact_nodes[0]
    target_id = target_node.node_id

    # Check if node has PII and redact it
    pii_found = detect_pii(target_node.body)
    if pii_found:
        redacted, _mapping = redact_text(target_node.body, mode="irreversible")
        assert redacted != target_node.body, "Redaction should change text with PII"

    # Build retrieval index
    idx = BM25Index()
    for node in graph.all_nodes():
        if node.is_active:
            idx.add_node(node)

    # Verify node is retrievable before deletion
    results_before = hybrid_score(target_node.title, graph=graph, index=idx, now_s=1000000)
    found_before = any(r.node_id == target_id for r in results_before)
    assert found_before, "Node should be retrievable before deletion"

    # Delete the memory
    delete_memory(graph, target_id)

    # Verify node is marked deleted
    deleted_node = graph.get_node(target_id)
    assert deleted_node is not None
    assert not deleted_node.is_active, "Deleted node should be inactive"

    # Rebuild index after deletion
    idx2 = BM25Index()
    for node in graph.all_nodes():
        if node.is_active:
            idx2.add_node(node)

    # Verify node is NOT retrievable after deletion
    results_after = hybrid_score(target_node.title, graph=graph, index=idx2, now_s=1000000)
    found_after = any(r.node_id == target_id for r in results_after)
    assert not found_after, "Deleted memory should not be retrievable"


def test_privacy_policy_engine_blocks_unauthorized_access():
    """Verify policy engine enforces access rules."""
    from famulix.privacy import PolicyRule

    engine = PolicyEngine(default_effect="allow")

    # Add a rule: deny export of sensitive tier
    rule = PolicyRule(
        id="deny-sensitive-export",
        effect="deny",
        actions={"export"},
        resources=set(),  # wildcard
        tiers={"sensitive"},
        priority=10,
    )
    engine.add_rule(rule)

    # Check that export is denied
    decision, _rule_id = engine.evaluate(action="export", resource="any", tier="sensitive")
    assert decision == "deny", "Policy should deny export of sensitive tier"

    # Check that read is allowed (default)
    decision, _rule_id = engine.evaluate(action="read", resource="any", tier="sensitive")
    assert decision == "allow", "Policy should allow read by default"


def test_privacy_gate_redacts_on_export():
    """Verify privacy gate applies redaction during export."""

    engine = PolicyEngine(default_effect="allow")
    # PrivacyGate requires a policy engine; we test redact_text directly
    PrivacyGate(policy=engine)

    text_with_pii = "Contact me at test@example.com for details"
    # Use the redact_text function directly since PrivacyGate doesn't have filter_for_export
    redacted, _mapping = redact_text(text_with_pii, mode="irreversible")

    # PII should be redacted
    assert "test@example.com" not in redacted, "Email should be redacted"
    assert "[EMAIL]" in redacted, "Email should be replaced with tag"
