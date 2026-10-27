"""Privacy and right-to-forget example.

Detects PII in a synthetic note, shows irreversible and reversible
redaction, then builds a small memory graph and deletes a fact with a
cascade, inspecting the tombstone and audit report.

Run: python examples/05_privacy_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from famulix.deletion import (
    delete_memory,
    deletion_audit_report,
    is_deleted,
    verify_deletion_cascade,
)
from famulix.events import note_event
from famulix.memory_graph import MemoryEdge, MemoryGraph, MemoryNode
from famulix.privacy import detect_pii, redact_text, restore_text

NOTE_TEXT = (
    "Contact me at alice.chen@example.com or 555-123-4567. "
    "Home address: 123 Oak Street. Card on file: 4111 1111 1111 1111."
)


def main() -> int:
    print("=== Privacy and Right-to-Forget Example ===")
    print()

    print("Original note:")
    print(f"  {NOTE_TEXT}")
    print()

    findings = detect_pii(NOTE_TEXT)
    print(f"PII detection: {len(findings)} item(s)")
    for match in findings:
        print(f"  {match.pii_type:8s} pos {match.start:3d}-{match.end:3d}  {match.text}")

    print()
    masked, _ = redact_text(NOTE_TEXT, "irreversible")
    print("Irreversible redaction:")
    print(f"  {masked}")

    tokenized, mapping = redact_text(NOTE_TEXT, "reversible", salt="demo-salt")
    print()
    print("Reversible redaction:")
    print(f"  {tokenized}")
    print(f"  tokens: {len(mapping)}")
    restored = restore_text(tokenized, mapping)
    print(f"  round-trip exact: {restored == NOTE_TEXT}")

    print()
    event = note_event(
        timestamp_s=1_700_000_000,
        source="phone",
        text=NOTE_TEXT,
    )
    graph = MemoryGraph()
    fact = MemoryNode.create(
        kind="fact",
        title="contact card",
        body=masked,
        created_at_s=1_700_000_000,
        metadata={"source_event": event.event_id, "tier": "private"},
    )
    episode = MemoryNode.create(
        kind="episode",
        title="privacy demo episode",
        body="redacted contact exchange",
        created_at_s=1_700_000_000,
    )
    graph.add_node(fact)
    graph.add_node(episode)
    graph.add_edge(MemoryEdge.create(episode.node_id, fact.node_id, "mentions"))
    print(f"Memory graph: {graph.node_count()} nodes")

    report = delete_memory(graph, fact.node_id)
    print()
    print("Deletion cascade:")
    print(f"  deleted nodes: {len(report.deleted_nodes)}")
    print(f"  cascaded edges: {len(report.deleted_edges)}")
    print(f"  tombstones: {len(report.tombstone_nodes)}")
    print(f"  tombstone blocks re-derivation: {is_deleted(graph, fact.node_id)}")

    audit = deletion_audit_report(graph)
    print()
    print("Audit report:")
    print(f"  total nodes: {audit['total_nodes']}")
    print(f"  deleted nodes: {audit['deleted_count']}")

    cascade = verify_deletion_cascade(graph, fact.node_id)
    print()
    print("Cascade verification:")
    for key, value in cascade.items():
        print(f"  {key}: {value}")

    print()
    print("Done. All operations were offline and deterministic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
