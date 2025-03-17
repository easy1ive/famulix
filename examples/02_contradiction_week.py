"""Contradiction week example.

Demonstrates how the memory system handles conflicting facts, the
supersede policy (newest-verified wins), and the deletion cascade.
Plants two conflicting facts a few days apart, runs consolidation,
and shows the audit trail.

Run: python examples/02_contradiction_week.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from famulix.deletion import delete_memory
from famulix.events import note_event
from famulix.memory_graph import MemoryGraph, MemoryNode


def main() -> int:
    print("=== Contradiction Week Example ===")
    print()

    g = MemoryGraph()

    # Day 1: old address
    old_note = note_event(
        timestamp_s=1_700_000_000,
        source="phone",
        text="home address: 123 Oak Street, Apt 4B",
    )
    old_fact = MemoryNode.create(
        kind="fact",
        title="home address",
        body="123 Oak Street, Apt 4B",
        created_at_s=1_700_000_000,
        metadata={"source_event": old_note.event_id, "trust": "medium"},
    )
    g.add_node(old_fact)
    print("Day 1: Added fact about home address")
    print(f"  id: {old_fact.node_id}")
    print(f"  value: {old_fact.body}")
    print()

    # Day 5: new address (conflicts)
    new_note = note_event(
        timestamp_s=1_700_000_000 + 4 * 86400,
        source="laptop",
        text="home address: 456 Pine Avenue, Suite 12",
    )
    new_fact = MemoryNode.create(
        kind="fact",
        title="home address",
        body="456 Pine Avenue, Suite 12",
        created_at_s=1_700_000_000 + 4 * 86400,
        metadata={"source_event": new_note.event_id, "trust": "high"},
    )
    g.add_node(new_fact)
    print("Day 5: Added conflicting fact about home address")
    print(f"  id: {new_fact.node_id}")
    print(f"  value: {new_fact.body}")
    print("  trust: high (more recent, laptop source)")
    print()

    # Show state before consolidation
    print(f"Before consolidation: {g.node_count()} fact nodes, all active")
    active_facts = [n for n in g.all_nodes() if n.kind == "fact" and n.is_active]
    for node in active_facts:
        print(f"  [{node.node_id[:12]}...] {node.title}: {node.body}")
    print()

    # Consolidate
    from famulix.consolidation import consolidate_graph

    report = consolidate_graph(g)
    print("After consolidation:")
    print(f"  Contradiction pairs resolved: {report.contradictions_resolved}")
    print(f"  Facts superseded: {len(report.superseded)}")
    print(f"  Facts merged (duplicates): {len(report.merged_pairs)}")
    print()

    # Show resolved state
    active_facts = [n for n in g.all_nodes() if n.kind == "fact" and n.is_active]
    print(f"Active facts: {len(active_facts)}")
    for node in active_facts:
        print(f"  [{node.node_id[:12]}...] {node.title}: {node.body}")

    inactive_facts = [n for n in g.all_nodes() if n.kind == "fact" and not n.is_active]
    if inactive_facts:
        print(f"Superseded facts: {len(inactive_facts)}")
        for node in inactive_facts:
            print(f"  [{node.node_id[:12]}...] {node.title}: {node.body}")
    print()

    # Deletion cascade
    print("=== Deletion Cascade Demo ===")
    target_fact = active_facts[0]
    print(f"Deleting the active fact ({target_fact.node_id[:12]}...)")
    audit = delete_memory(g, target_fact.node_id)
    print(f"  Nodes deleted: {len(audit.deleted_nodes)}")
    print(f"  Edges deleted: {len(audit.deleted_edges)}")
    print(f"  Tombstones created: {len(audit.tombstone_nodes)}")

    # Verify the old superseded fact stays deleted too
    old_node = g.get_node(old_fact.node_id)
    target_node = g.get_node(target_fact.node_id)
    print(f"  Other fact remains inactive: {old_node is not None and not old_node.is_active}")
    print(f"  Deleted fact retained as tombstone: {target_node is not None}")
    if target_node:
        print(f"  Deleted fact is_active: {target_node.is_active}")
        print(f"  Deleted fact metadata deleted: {target_node.metadata.get('deleted')}")
    print()

    print("=== Done ===")
    print("Summary:")
    print("  1. Two conflicting facts about the same key are detected")
    print("  2. Newest-verified-wins policy selects the active version")
    print("  3. Deletion cascades and leaves tombstones for audit")
    print()
    print("Note: All data is synthetic. This demonstrates mechanics, not")
    print("      any real-user scenario or LLM capability.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
