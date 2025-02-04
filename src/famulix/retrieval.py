"""Hybrid retrieval: BM25 + recency/salience fusion + MMR diversification.

Reference: BM25 (Robertson & Zaragoza 2009), MMR diversification
(Carbonell & Goldstein 1998).
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass

from famulix.memory_graph import MemoryGraph, MemoryNode


def tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer, lowercased."""
    text = text.lower()
    tokens = re.findall(r"[\w一-鿿]+", text)
    return tokens


@dataclass
class RetrievalResult:
    """A single retrieval hit with citation payload."""

    node_id: str
    score: float
    citation: str

    def as_dict(self) -> dict[str, object]:
        return {"node_id": self.node_id, "score": round(self.score, 6), "citation": self.citation}


class BM25Index:
    """A simple BM25 inverted index over memory node text."""

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.docs: dict[str, list[str]] = {}  # node_id -> tokens
        self.df: dict[str, int] = {}  # term -> document frequency
        self.avgdl: float = 0.0
        self._doc_lens: dict[str, int] = {}

    def add(self, node_id: str, text: str) -> None:
        tokens = tokenize(text)
        if node_id in self.docs:
            self._remove_from_df(node_id)
        self.docs[node_id] = tokens
        self._doc_lens[node_id] = len(tokens)
        seen: set[str] = set()
        for t in tokens:
            if t not in seen:
                self.df[t] = self.df.get(t, 0) + 1
                seen.add(t)
        self._recompute_avgdl()

    def add_node(self, node: MemoryNode) -> None:
        text = f"{node.title} {node.body}"
        self.add(node.node_id, text)

    def _remove_from_df(self, node_id: str) -> None:
        if node_id not in self.docs:
            return
        tokens = self.docs[node_id]
        seen: set[str] = set()
        for t in tokens:
            if t not in seen:
                self.df[t] = max(self.df.get(t, 0) - 1, 0)
                seen.add(t)

    def _recompute_avgdl(self) -> None:
        if not self._doc_lens:
            self.avgdl = 0.0
            return
        self.avgdl = sum(self._doc_lens.values()) / len(self._doc_lens)

    def score(self, query: str) -> dict[str, float]:
        """Return BM25 scores for all docs for the given query."""
        q_tokens = tokenize(query)
        n_docs = len(self.docs)
        scores: dict[str, float] = {did: 0.0 for did in self.docs}
        for term in q_tokens:
            df = self.df.get(term, 0)
            if df == 0:
                continue
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
            for doc_id, tokens in self.docs.items():
                tf = tokens.count(term)
                dl = self._doc_lens[doc_id]
                denom = tf + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1.0))
                scores[doc_id] += idf * (tf * (self.k1 + 1)) / denom
        return {k: round(v, 6) for k, v in scores.items() if v > 0}

    def remove(self, node_id: str) -> None:
        if node_id not in self.docs:
            return
        self._remove_from_df(node_id)
        del self.docs[node_id]
        del self._doc_lens[node_id]
        self._recompute_avgdl()


@dataclass(frozen=True)
class FusionConfig:
    """Weights for hybrid score fusion."""

    bm25_weight: float = 0.5
    recency_weight: float = 0.2
    salience_weight: float = 0.3


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    """Min-max normalize a score dict to [0, 1]."""
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


def hybrid_score(
    query: str,
    *,
    graph: MemoryGraph,
    index: BM25Index,
    now_s: int,
    config: FusionConfig | None = None,
    candidate_kinds: Iterable[str] | None = None,
) -> list[RetrievalResult]:
    """Compute hybrid retrieval scores for a query.

    Combines BM25 relevance, recency, and salience via weighted sum of
    normalized components. Returns results sorted by descending score.
    """
    cfg = config or FusionConfig()
    kinds = set(candidate_kinds) if candidate_kinds else None

    # BM25
    bm25_raw = index.score(query)

    # Recency: 1.0 for newest, decaying by age
    recency_raw: dict[str, float] = {}
    for node in graph.all_nodes():
        if not node.is_active:
            continue
        if kinds and node.kind not in kinds:
            continue
        age = max(now_s - node.created_at_s, 0)
        recency_raw[node.node_id] = math.exp(-age / 86400.0)  # 1-day half-life-ish

    # Salience proxy: use degree + content length
    from famulix.salience import compute_salience

    salience_raw: dict[str, float] = {}
    for node in graph.all_nodes():
        if not node.is_active:
            continue
        if kinds and node.kind not in kinds:
            continue
        salience_raw[node.node_id] = compute_salience(node, graph=graph, now_s=now_s)

    # Normalize and fuse — only over shared keys
    all_keys = set(bm25_raw) | set(recency_raw) | set(salience_raw)
    bm25_norm = _normalize(bm25_raw)
    recency_norm = _normalize(recency_raw)
    salience_norm = _normalize(salience_raw)

    fused: dict[str, float] = {}
    for key in all_keys:
        b = bm25_norm.get(key, 0.0)
        r = recency_norm.get(key, 0.0)
        s = salience_norm.get(key, 0.0)
        fused[key] = round(
            cfg.bm25_weight * b + cfg.recency_weight * r + cfg.salience_weight * s, 6
        )

    # Verify citations resolve to existing nodes
    results = []
    for nid, score in sorted(fused.items(), key=lambda x: x[1], reverse=True):
        node = graph.get_node(nid)
        if node is None or not node.is_active:
            continue
        citation = f"[{node.kind}] {node.title}"
        results.append(RetrievalResult(node_id=nid, score=score, citation=citation))
    return results


def mmr_rerank(
    results: list[RetrievalResult],
    *,
    graph: MemoryGraph,
    lambda_param: float = 0.7,
    top_k: int = 10,
) -> list[RetrievalResult]:
    """Diversify results using Maximal Marginal Relevance.

    Diversity is measured via text similarity between node bodies; MMR trades
    off relevance against similarity to already-selected items.
    """
    if not results:
        return []
    top_k = min(top_k, len(results))
    selected: list[str] = []
    remaining = [r.node_id for r in results]
    score_map = {r.node_id: r.score for r in results}
    citation_map = {r.node_id: r.citation for r in results}

    # Precompute text similarity cache
    def node_text(nid: str) -> str:
        n = graph.get_node(nid)
        return f"{n.title} {n.body}" if n else ""

    sim_cache: dict[tuple[str, str], float] = {}

    def similarity(a: str, b: str) -> float:
        key = (a, b) if a < b else (b, a)
        if key in sim_cache:
            return sim_cache[key]
        ta = set(tokenize(node_text(a)))
        tb = set(tokenize(node_text(b)))
        s = 0.0 if not ta or not tb else len(ta & tb) / len(ta | tb)
        sim_cache[key] = s
        return s

    selected_results: list[RetrievalResult] = []
    for _ in range(top_k):
        if not remaining:
            break
        best_id = None
        best_mmr = -math.inf
        for nid in remaining:
            relevance = score_map.get(nid, 0.0)
            max_sim = max((similarity(nid, s) for s in selected), default=0.0)
            mmr_val = lambda_param * relevance - (1 - lambda_param) * max_sim
            if mmr_val > best_mmr:
                best_mmr = mmr_val
                best_id = nid
        if best_id is None:
            break
        selected.append(best_id)
        remaining.remove(best_id)
        selected_results.append(
            RetrievalResult(
                node_id=best_id,
                score=round(score_map.get(best_id, 0.0), 6),
                citation=citation_map.get(best_id, ""),
            )
        )
    return selected_results


def parse_query(text: str) -> dict[str, object]:
    """Parse a query string for structured filters.

    Supports:
    - tag:xxx  → filter by metadata tag
    - kind:fact → filter by node kind
    - since:YYYY-MM-DD → time window start
    - until:YYYY-MM-DD → time window end
    """
    parts = text.split()
    filters: dict[str, object] = {
        "terms": [],
        "kinds": [],
        "tags": [],
        "since": None,
        "until": None,
    }
    for part in parts:
        if part.startswith("kind:"):
            filters["kinds"].append(part[5:])  # type: ignore[attr-defined]
        elif part.startswith("tag:"):
            filters["tags"].append(part[4:])  # type: ignore[attr-defined]
        elif part.startswith("since:"):
            filters["since"] = part[6:]
        elif part.startswith("until:"):
            filters["until"] = part[6:]
        else:
            filters["terms"].append(part)  # type: ignore[attr-defined]
    return filters
