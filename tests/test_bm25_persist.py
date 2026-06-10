"""Tests for BM25 index persistence."""

import tempfile
from pathlib import Path

from famulix.bm25_persist import index_needs_rebuild, load_index, save_index
from famulix.retrieval import BM25Index


def test_save_load_roundtrip():
    idx = BM25Index()
    idx.add("n1", "hello world")
    idx.add("n2", "foo bar baz")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = Path(f.name)

    save_index(idx, path)
    loaded = load_index(path)

    assert loaded.k1 == idx.k1
    assert loaded.b == idx.b
    assert loaded.docs == idx.docs

    path.unlink()


def test_index_needs_rebuild_detects_stale():
    idx = BM25Index()
    idx.add("n1", "hello")
    idx.add("n2", "world")

    assert not index_needs_rebuild(idx, {"n1", "n2"})
    assert index_needs_rebuild(idx, {"n1"})
    assert index_needs_rebuild(idx, {"n1", "n2", "n3"})
