"""Tests for BM25 index save/load persistence round-trip."""

from pathlib import Path

from famulix.retrieval import BM25Index


def test_save_and_load_roundtrip(tmp_path: Path):
    index = BM25Index()
    index.add("doc1", "the quick brown fox")
    index.add("doc2", "lazy dog sleeps all day")
    index.add("doc3", "brown fox and lazy dog")

    path = tmp_path / "index.json"
    index.save(str(path))
    loaded = BM25Index.load(str(path))

    assert loaded.doc_count == index.doc_count
    # Scores should be identical
    s1 = index.score("fox")
    s2 = loaded.score("fox")
    assert s1 == s2


def test_save_and_load_empty_index(tmp_path: Path):
    index = BM25Index()
    path = tmp_path / "empty.json"
    index.save(str(path))
    loaded = BM25Index.load(str(path))
    assert loaded.doc_count == 0


def test_loaded_index_can_be_searched(tmp_path: Path):
    index = BM25Index()
    index.add("m1", "home address 123 oak street")
    index.add("m2", "phone number 555-0100")
    index.add("m3", "email user@example.com")

    path = tmp_path / "index.json"
    index.save(str(path))
    loaded = BM25Index.load(str(path))

    scores = loaded.score("address")
    assert "m1" in scores
    assert scores["m1"] > 0.0


def test_save_overwrites_existing(tmp_path: Path):
    path = tmp_path / "index.json"

    idx1 = BM25Index()
    idx1.add("a", "hello world")
    idx1.save(str(path))

    idx2 = BM25Index()
    idx2.add("b", "goodbye world")
    idx2.add("c", "hello again")
    idx2.save(str(path))

    loaded = BM25Index.load(str(path))
    assert loaded.doc_count == 2
    assert "b" in loaded.score("goodbye")
