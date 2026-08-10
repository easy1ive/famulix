"""Property test: deleted memories never reappear through any query path.

Tests recall, context assembly, and export after deletion.
"""

import pytest

from famulix.context import ContextItem, assemble_context
from famulix.deletion import delete_memory, is_deleted
from famulix.memory_graph import MemoryGraph, MemoryNode
from famulix.retrieval import BM25Index, query_with_filters


@pytest.fixture
def graph_with_deletable():
    g = MemoryGraph()
    n1 = MemoryNode(
        node_id="mem_live",
        kind="fact",
        title="address",
        body="123 Oak St",
        created_at_s=1000,
    )
    n2 = MemoryNode(
        node_id="mem_delete",
        kind="fact",
        title="phone",
        body="555-0100",
        created_at_s=1001,
    )
    n3 = MemoryNode(
        node_id="mem_other",
        kind="fact",
        title="email",
        body="a@b.com",
        created_at_s=1002,
    )
    g.add_node(n1)
    g.add_node(n2)
    g.add_node(n3)
    return g


def test_deleted_not_in_recall(graph_with_deletable):
    g = graph_with_deletable
    delete_memory(g, "mem_delete", cascade=True)
    index = BM25Index()
    for node in g.active_nodes():
        index.add(node.node_id, f"{node.title} {node.body}")
    results = query_with_filters(
        "phone number",
        graph=g,
        index=index,
        now_s=2000,
        max_results=10,
    )
    ids = [r.node_id for r in results]
    assert "mem_delete" not in ids


def test_deleted_not_in_context(graph_with_deletable):
    g = graph_with_deletable
    delete_memory(g, "mem_delete", cascade=True)
    items = [
        ContextItem(
            item_id=n.node_id,
            payload=f"{n.title} {n.body}",
            token_estimate=10,
            value=1.0,
        )
        for n in g.active_nodes()
    ]
    result = assemble_context(items, budget=500)
    ids = [item.item_id for item in result.items]
    assert "mem_delete" not in ids


def test_deleted_not_in_active_nodes(graph_with_deletable):
    g = graph_with_deletable
    delete_memory(g, "mem_delete", cascade=True)
    active_ids = {n.node_id for n in g.active_nodes()}
    assert "mem_delete" not in active_ids
    assert "mem_live" in active_ids
    assert "mem_other" in active_ids


def test_deleted_is_marked(graph_with_deletable):
    g = graph_with_deletable
    delete_memory(g, "mem_delete", cascade=True)
    assert is_deleted(g, "mem_delete")
    assert not is_deleted(g, "mem_live")


def test_deleted_not_in_export(graph_with_deletable):
    g = graph_with_deletable
    delete_memory(g, "mem_delete", cascade=True)
    exported = g.to_dict()
    active_ids = {
        n["node_id"]
        for n in exported["nodes"]
        if n.get("is_active", True) and not n.get("deleted", False)
    }
    assert "mem_delete" not in active_ids
