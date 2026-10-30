# Privacy and Deletion

famulix implements GDPR-style privacy tiers and right-to-forget deletion
semantics with audit trails and resurrection prevention.

## Privacy Tiers

Memories are assigned to privacy tiers:

- **public**: Can be exported, shared, and cited freely
- **internal**: Can be read and cited, but not exported
- **sensitive**: Read-only, redacted on export
- **restricted**: No access without explicit approval

## PII Detection

`detect_pii()` identifies personally identifiable information:

```python
from famulix.privacy import detect_pii

text = "Contact me at user@example.com or call 555-0123"
findings = detect_pii(text)
for f in findings:
    print(f"{f.pii_type}: {f.start}-{f.end}")
```

Detected types:
- `email`: Email addresses
- `phone`: Phone numbers (various formats)
- `card`: Credit card numbers (with Luhn validation)
- `address`: Street addresses

## Redaction

`redact_text()` replaces PII with tags or reversible tokens:

```python
from famulix.privacy import redact_text

# Irreversible: replaces with type tags
redacted, _ = redact_text(text, mode="irreversible")
# "Contact me at [EMAIL] or call [PHONE]"

# Reversible: replaces with hash tokens, returns mapping
redacted, mapping = redact_text(text, mode="reversible", salt="secret")
# "Contact me at tok_abc123 or call tok_def456"
# mapping = {"tok_abc123": "user@example.com", ...}
```

## Policy Engine

The `PolicyEngine` evaluates access requests:

```python
from famulix.privacy import PolicyEngine, PolicyRule

engine = PolicyEngine(default_effect="deny")
engine.add_rule(
    PolicyRule(
        id="allow-public-read",
        effect="allow",
        actions={"read"},
        resources=set(),  # wildcard
        tiers={"public"},
        priority=10,
    )
)

decision, rule_id = engine.evaluate(
    action="read",
    resource="memory_123",
    tier="public",
)
print(decision)  # "allow"
```

Rules are evaluated in priority order (highest first). Empty match sets act as
wildcards.

## Privacy Gate

The `PrivacyGate` wraps the policy engine and applies redaction:

```python
from famulix.privacy import PrivacyGate, PolicyEngine

engine = PolicyEngine(default_effect="allow")
gate = PrivacyGate(policy=engine)

# Check if an action is allowed
allowed = gate.check(action="export", resource="memory_123", tier="sensitive")
```

## Deletion Semantics

`delete_memory()` cascades deletion across the graph:

```python
from famulix.deletion import delete_memory

delete_memory(graph, "mem_abc123")
```

This:
1. Marks the target node as inactive (`is_active=False`)
2. Removes all edges to/from the node
3. Removes the node from the BM25 retrieval index
4. Adds a tombstone to prevent re-derivation

## Tombstones

Deleted nodes remain in the graph as inactive tombstones. This prevents:
- Re-encoding from surviving events
- Re-derivation through consolidation
- Resurrection through retrieval

```python
node = graph.get_node("mem_abc123")
assert node is not None  # Tombstone exists
assert not node.is_active  # But inactive
```

## Right-to-Forget Cascade

Deletion cascades across:
- Memory graph nodes and edges
- BM25 retrieval index
- Consolidation reports (superseded references)
- Briefing citations (removed from future briefings)
- Session logs (marked as deleted)

## Audit Trail

Every deletion is logged with:
- Node ID
- Timestamp
- Reason (if provided)
- Cascade count (edges removed)

```python
from famulix.deletion import deletion_audit_log

log = deletion_audit_log(graph)
for entry in log:
    print(f"{entry.node_id}: {entry.reason} ({entry.edges_removed} edges)")
```

## Property Tests

The test suite verifies:
- Deleted memories never reappear through any query path
- Privacy tiers never leak to lower tiers
- Citations always resolve to live (non-deleted) memories
- Redaction is reversible with the correct salt

## Access Log

The `AccessLog` records every access attempt:

```python
from famulix.privacy import AccessLog

log = AccessLog()
log.record(action="read", resource="mem_123", tier="sensitive", decision="allow")
log.record(action="export", resource="mem_123", tier="sensitive", decision="deny")

# Query the log
denied = [e for e in log.entries if e.decision == "deny"]
```

The access log is immutable — entries cannot be modified or deleted.
