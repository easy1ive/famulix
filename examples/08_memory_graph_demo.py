#!/usr/bin/env python3
"""Example 08: Memory graph demonstration.

Demonstrates building and querying a memory graph.
"""

from famulix.memory_graph import MemoryGraph, MemoryNode, export_graph_summary


def main() -> None:
    """Run memory graph demonstration."""
    print("=== Memory Graph Demo ===\n")

    graph = MemoryGraph()

    # Add some nodes
    graph.add_node(MemoryNode.create(kind="fact", title="User's name", body="Alice"))
    graph.add_node(MemoryNode.create(kind="fact", title="Favorite color", body="Blue"))
    graph.add_node(
        MemoryNode.create(kind="preference", title="Morning meetings", body="Prefers 9am")
    )

    print(export_graph_summary(graph))
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
