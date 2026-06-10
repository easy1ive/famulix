"""BM25 index persistence: save and load index state."""

from __future__ import annotations

import json
from pathlib import Path

from famulix.retrieval import BM25Index


def save_index(index: BM25Index, path: Path) -> None:
    """Save a BM25 index to disk as JSON."""
    data = {
        "k1": index.k1,
        "b": index.b,
        "docs": index.docs,
        "df": index.df,
        "avgdl": index.avgdl,
        "doc_lens": index._doc_lens,
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def load_index(path: Path) -> BM25Index:
    """Load a BM25 index from disk."""
    data = json.loads(path.read_text())
    index = BM25Index(k1=data["k1"], b=data["b"])
    index.docs = data["docs"]
    index.df = data["df"]
    index.avgdl = data["avgdl"]
    index._doc_lens = data["doc_lens"]
    return index


def index_needs_rebuild(index: BM25Index, node_ids: set[str]) -> bool:
    """Check if index is stale (missing nodes or has deleted nodes)."""
    indexed_ids = set(index.docs.keys())
    return indexed_ids != node_ids
