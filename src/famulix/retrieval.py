"""Hybrid retrieval: BM25 + recency/salience fusion + MMR diversification.

Reference: BM25 (Robertson & Zaragoza 2009), MMR diversification
(Carbonell & Goldstein 1998).
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

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

    @property
    def doc_count(self) -> int:
        return len(self.docs)

    @property
    def term_count(self) -> int:
        return len(self.df)

    def doc_len(self, node_id: str) -> int:
        return self._doc_lens.get(node_id, 0)

    def top_terms(self, k: int = 10) -> list[tuple[str, int]]:
        """Return the k most frequent terms by document frequency."""
        terms = sorted(self.df.items(), key=lambda pair: (-pair[1], pair[0]))
        return terms[: max(k, 0)]

    def save(self, path: str | Path) -> None:
        """Persist the index to a JSON file for later reload."""
        payload = {
            "schema_version": 1,
            "k1": self.k1,
            "b": self.b,
            "docs": {nid: tokens for nid, tokens in self.docs.items()},
            "df": dict(self.df),
            "doc_lens": dict(self._doc_lens),
            "avgdl": self.avgdl,
        }
        Path(path).write_text(
            json.dumps(payload, sort_keys=True, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: str | Path) -> BM25Index:
        """Reload a previously saved index. Raises on schema mismatch."""
        text = Path(path).read_text(encoding="utf-8")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid BM25 index JSON") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("unsupported BM25 index schema version")
        required = {"schema_version", "k1", "b", "docs", "df", "doc_lens", "avgdl"}
        if set(payload) != required:
            raise ValueError("BM25 index payload has unknown or missing fields")
        index = cls(k1=float(payload["k1"]), b=float(payload["b"]))
        index.docs = {str(nid): list(tokens) for nid, tokens in payload["docs"].items()}
        index.df = {str(term): int(freq) for term, freq in payload["df"].items()}
        index._doc_lens = {str(nid): int(length) for nid, length in payload["doc_lens"].items()}
        index.avgdl = float(payload["avgdl"])
        return index

    def stale_ids(self, live_ids: set[str]) -> set[str]:
        """Return indexed node ids that are no longer live (deleted or inactive)."""
        return set(self.docs) - live_ids

    def rebuild_from_graph(self, graph: MemoryGraph) -> int:
        """Clear and re-index every active node. Returns the count re-indexed."""
        self.docs.clear()
        self.df.clear()
        self._doc_lens.clear()
        self.avgdl = 0.0
        count = 0
        for node in graph.all_nodes():
            if not node.is_active:
                continue
            self.add_node(node)
            count += 1
        return count

    def prune_stale(self, live_ids: set[str]) -> int:
        """Remove entries for nodes that no longer exist. Returns count pruned."""
        stale = self.stale_ids(live_ids)
        for nid in stale:
            self.remove(nid)
        return len(stale)


@dataclass(frozen=True)
class FusionConfig:
    """Weights for hybrid score fusion, normalized by their configured sum."""

    bm25_weight: float = 0.5
    recency_weight: float = 0.2
    salience_weight: float = 0.3

    def __post_init__(self) -> None:
        weights = (self.bm25_weight, self.recency_weight, self.salience_weight)
        if any(not math.isfinite(weight) or weight < 0 for weight in weights):
            raise ValueError("fusion weights must be finite and non-negative")
        if sum(weights) <= 0:
            raise ValueError("at least one fusion weight must be positive")


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
    live_ids = {
        node.node_id
        for node in graph.all_nodes()
        if node.is_active and (kinds is None or node.kind in kinds)
    }
    bm25_raw = {node_id: score for node_id, score in bm25_raw.items() if node_id in live_ids}

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
    results: list[RetrievalResult] = []
    for nid, score in sorted(fused.items(), key=lambda x: (-x[1], x[0])):
        result_node = graph.get_node(nid)
        if result_node is None or not result_node.is_active:
            continue
        citation = f"[{result_node.kind}] {result_node.title}"
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
    remaining = sorted(r.node_id for r in results)
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
    - "quoted phrase" → exact phrase match (stored in phrases)
    - -term → negated term (excluded from results)
    """
    terms: list[str] = []
    phrases: list[str] = []
    negated: list[str] = []
    kinds: list[str] = []
    tags: list[str] = []
    since: str | None = None
    until: str | None = None

    in_quote = False
    current_phrase: list[str] = []
    for part in text.split():
        if in_quote:
            if part.endswith('"'):
                current_phrase.append(part[:-1])
                phrases.append(" ".join(current_phrase))
                current_phrase = []
                in_quote = False
            else:
                current_phrase.append(part)
        elif part.startswith('"'):
            if part.endswith('"') and len(part) > 1:
                phrases.append(part[1:-1])
            else:
                current_phrase.append(part[1:])
                in_quote = True
        elif part.startswith("-") and len(part) > 1:
            negated.append(part[1:])
        elif part.startswith("kind:"):
            kinds.append(part[len("kind:") :])
        elif part.startswith("tag:"):
            tags.append(part[len("tag:") :])
        elif part.startswith("since:"):
            since = part[len("since:") :]
        elif part.startswith("until:"):
            until = part[len("until:") :]
        else:
            terms.append(part)
    if current_phrase:
        phrases.append(" ".join(current_phrase))
    return {
        "terms": terms,
        "phrases": phrases,
        "negated": negated,
        "kinds": kinds,
        "tags": tags,
        "since": since,
        "until": until,
    }


def query_with_filters(
    query_text: str,
    *,
    graph: MemoryGraph,
    index: BM25Index,
    now_s: int,
    config: FusionConfig | None = None,
    max_results: int = 20,
) -> list[RetrievalResult]:
    """Run a parsed query against the hybrid retrieval with filters applied."""
    parsed = parse_query(query_text)
    raw_terms = parsed.get("terms")
    terms = " ".join(str(term) for term in raw_terms) if isinstance(raw_terms, list) else ""
    raw_kinds = parsed.get("kinds")
    kinds = [str(kind) for kind in raw_kinds] if isinstance(raw_kinds, list) and raw_kinds else None
    raw_tags = parsed.get("tags")
    tags = {str(tag) for tag in raw_tags} if isinstance(raw_tags, list) else set()
    raw_phrases = parsed.get("phrases")
    phrases = [str(p) for p in raw_phrases] if isinstance(raw_phrases, list) else []
    raw_negated = parsed.get("negated")
    negated = [str(n) for n in raw_negated] if isinstance(raw_negated, list) else []

    results = hybrid_score(
        terms or query_text,
        graph=graph,
        index=index,
        now_s=now_s,
        config=config,
        candidate_kinds=kinds,
    )

    if tags:
        tagged: list[RetrievalResult] = []
        for result in results:
            node = graph.get_node(result.node_id)
            if node is None:
                continue
            if str(node.metadata.get("tag", "")) in tags:
                tagged.append(result)
        results = tagged

    if phrases:
        phrase_filtered: list[RetrievalResult] = []
        for result in results:
            node = graph.get_node(result.node_id)
            if node is None:
                continue
            text_lower = f"{node.title} {node.body}".lower()
            if all(phrase.lower() in text_lower for phrase in phrases):
                phrase_filtered.append(result)
        results = phrase_filtered

    if negated:
        neg_filtered: list[RetrievalResult] = []
        for result in results:
            node = graph.get_node(result.node_id)
            if node is None:
                continue
            text_lower = f"{node.title} {node.body}".lower()
            if not any(term.lower() in text_lower for term in negated):
                neg_filtered.append(result)
        results = neg_filtered

    return results[:max_results]


Reranker = Callable[[list[RetrievalResult], MemoryGraph], list[RetrievalResult]]


def apply_reranker(
    results: list[RetrievalResult],
    *,
    graph: MemoryGraph,
    reranker: Reranker,
) -> list[RetrievalResult]:
    """Apply a pluggable reranker under citation-safety constraints.

    The reranker may reorder or drop hits but can never invent them: every
    returned id must appear in the input, must still resolve to an active
    node, and may appear only once. Violations raise ValueError so a learned
    or scripted reranker cannot smuggle citations to unknown or deleted
    memories. The input list itself is not mutated.
    """
    reranked = reranker(list(results), graph)
    allowed = {result.node_id for result in results}
    seen: set[str] = set()
    output: list[RetrievalResult] = []
    for result in reranked:
        if result.node_id not in allowed:
            raise ValueError(f"reranker invented unknown result: {result.node_id}")
        if result.node_id in seen:
            raise ValueError(f"reranker duplicated result: {result.node_id}")
        node = graph.get_node(result.node_id)
        if node is None or not node.is_active:
            raise ValueError(f"reranker returned non-active memory: {result.node_id}")
        seen.add(result.node_id)
        output.append(result)
    return output
