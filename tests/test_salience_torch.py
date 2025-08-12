"""Tests for the optional PyTorch salience module.

All tests skip when torch is not installed.
Marked as model tests (part of test-all, excluded from fast test).
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.model, pytest.mark.slow]

torch = pytest.importorskip("torch", reason="torch extra not installed")

from famulix.memory_graph import MemoryGraph, MemoryNode  # noqa: E402
from famulix.salience_torch import (  # noqa: E402
    SalienceMLP,
    TorchSalienceConfig,
    _extract_features,
    is_torch_available,
    train_demo_synthetic,
)


def test_is_torch_available_true_when_imported():
    assert is_torch_available() is True


def test_extract_features_dimensions():
    node = MemoryNode.create(
        kind="fact",
        title="test node",
        body="this is a test body with some content",
        created_at_s=1000,
    )
    feats = _extract_features(node, now_s=2000, freq=1.0)
    assert len(feats) == 10
    assert all(0.0 <= f <= 1.0 for f in feats)


def test_extract_features_recency_decreases_with_age():
    node = MemoryNode.create(kind="fact", title="t", body="b", created_at_s=0)
    recent = _extract_features(node, now_s=100, freq=1.0)[0]
    older = _extract_features(node, now_s=100000, freq=1.0)[0]
    assert recent > older


def test_extract_features_pinned_flag():
    unpinned = MemoryNode.create(kind="fact", title="t", body="b", created_at_s=0)
    pinned = MemoryNode.create(
        kind="fact",
        title="t",
        body="b",
        created_at_s=0,
        metadata={"pinned": "true"},
    )
    assert _extract_features(unpinned, now_s=10)[5] == 0.0
    assert _extract_features(pinned, now_s=10)[5] == 1.0


def test_extract_features_commitment_language():
    normal = MemoryNode.create(kind="fact", title="t", body="some regular text", created_at_s=0)
    urgent = MemoryNode.create(
        kind="fact",
        title="t",
        body="this is urgent must do deadline",
        created_at_s=0,
    )
    assert _extract_features(normal, now_s=10)[6] == 0.0
    assert _extract_features(urgent, now_s=10)[6] == 1.0


def test_salience_mlp_init():
    config = TorchSalienceConfig(input_dim=10, hidden_dim=16, num_layers=2)
    model = SalienceMLP(config)
    assert model.config == config
    assert model.model is not None


def test_salience_mlp_score_node_returns_float():
    model = SalienceMLP(TorchSalienceConfig(seed=42))
    node = MemoryNode.create(kind="fact", title="test", body="test body", created_at_s=100)
    score = model.score_node(node, now_s=1000)
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_salience_mlp_score_deterministic_same_seed():
    m1 = SalienceMLP(TorchSalienceConfig(seed=42))
    m2 = SalienceMLP(TorchSalienceConfig(seed=42))
    node = MemoryNode.create(kind="fact", title="test", body="test body", created_at_s=100)
    assert m1.score_node(node, now_s=1000) == m2.score_node(node, now_s=1000)


def test_salience_mlp_score_different_seeds():
    m1 = SalienceMLP(TorchSalienceConfig(seed=1))
    m2 = SalienceMLP(TorchSalienceConfig(seed=99))
    node = MemoryNode.create(kind="fact", title="test", body="test body", created_at_s=100)
    s1 = m1.score_node(node, now_s=1000)
    s2 = m2.score_node(node, now_s=1000)
    assert s1 != s2


def test_salience_mlp_score_all_graph():
    g = MemoryGraph()
    for i in range(5):
        node = MemoryNode.create(
            kind="fact",
            title=f"node_{i}",
            body=f"body {i}",
            created_at_s=i * 100,
        )
        g.add_node(node)
    model = SalienceMLP(TorchSalienceConfig(seed=0))
    scores = model.score_all(g, now_s=500)
    assert len(scores) == 5
    for nid, score in scores.items():
        assert g.has_node(nid)
        assert 0.0 <= score <= 1.0


def test_train_demo_shows_loss_decrease():
    model, losses = train_demo_synthetic(num_nodes=30, seed=42)
    assert len(losses) > 1
    first_third = sum(losses[: len(losses) // 3])
    last_third = sum(losses[-len(losses) // 3 :])
    assert last_third < first_third
    assert losses[-1] < losses[0]


def test_train_on_graphs_mismatched_lengths_raises():
    model = SalienceMLP()
    g = MemoryGraph()
    with pytest.raises(ValueError, match="same length"):
        model.train_on_graphs([g, g], [{}], now_s=0)


def test_train_on_graphs_empty_data_returns_empty():
    model = SalienceMLP()
    g = MemoryGraph()
    losses = model.train_on_graphs([g], [{}], now_s=0)
    assert losses == []


def test_mlp_vs_numpy_both_produce_scores():
    """Compare torch MLP and numpy scorer: both produce valid scores."""
    from famulix.salience import score_all_nodes

    g = MemoryGraph()
    for i in range(10):
        node = MemoryNode.create(
            kind="fact",
            title=f"item {i}",
            body=f"some content about item {i} with varying importance",
            created_at_s=i * 3600,
            metadata={"pinned": "true"} if i % 3 == 0 else {},
        )
        g.add_node(node)

    numpy_scores = score_all_nodes(g, now_s=40000)
    model = SalienceMLP(TorchSalienceConfig(seed=0))
    torch_scores = model.score_all(g, now_s=40000)

    assert len(numpy_scores) == len(torch_scores)
    assert all(0 <= v <= 1 for v in numpy_scores.values())
    assert all(0 <= v <= 1 for v in torch_scores.values())
    assert set(numpy_scores.keys()) == set(torch_scores.keys())


from famulix.salience_torch import (  # noqa: E402
    RankFusionMLP,
    TorchRankFusionConfig,
    _planted_pair_rule,
    rank_fusion_pair_accuracy,
    train_rank_fusion_demo,
)


def test_rank_fusion_demo_loss_decreases() -> None:
    """Training on the planted synthetic rule measurably lowers the loss."""
    _model, losses = train_rank_fusion_demo(num_pairs=200, seed=42)
    assert losses, "demo should report per-epoch losses"
    assert losses[-1] < losses[0], f"loss did not decrease: {losses[0]} -> {losses[-1]}"


def test_rank_fusion_demo_is_deterministic() -> None:
    first, losses_a = train_rank_fusion_demo(num_pairs=80, seed=7)
    second, losses_b = train_rank_fusion_demo(num_pairs=80, seed=7)
    assert losses_a == losses_b
    rows = [[0.9, 0.1, 0.5], [0.2, 0.8, 0.3]]
    assert first.score_rows(rows) == second.score_rows(rows)


def test_rank_fusion_beats_linear_baseline_on_planted_rule() -> None:
    """Measured comparison on synthetic pairs; not a claim about real data."""
    import random

    rng = random.Random(1234)
    eval_pairs: list[tuple[list[float], list[float]]] = []
    for _ in range(300):
        a = [rng.random(), rng.random(), rng.random()]
        b = [rng.random(), rng.random(), rng.random()]
        winner, loser = (a, b) if _planted_pair_rule(a, b) else (b, a)
        eval_pairs.append((winner, loser))
    model, _losses = train_rank_fusion_demo(num_pairs=400, seed=11)
    learned = rank_fusion_pair_accuracy(model, eval_pairs)

    def linear(row: list[float]) -> float:
        return 0.5 * row[0] + 0.2 * row[1] + 0.3 * row[2]

    baseline_hits = sum(1 for win, lose in eval_pairs if linear(win) > linear(lose))
    baseline = round(baseline_hits / len(eval_pairs), 6)
    assert learned >= baseline
    assert learned > 0.85


def test_rank_fusion_rank_orders_and_tiebreaks_by_id() -> None:
    model = RankFusionMLP(TorchRankFusionConfig(epochs=0))
    assert model.rank({}) == []
    candidates = {"b": [0.1, 0.1, 0.1], "a": [0.1, 0.1, 0.1]}
    assert model.rank(candidates) == ["a", "b"]


def test_rank_fusion_training_validation() -> None:
    model = RankFusionMLP()
    with pytest.raises(ValueError):
        model.train_on_pairs([[0.1, 0.2, 0.3]], [])
    assert model.train_on_pairs([], []) == []
    assert model.score_rows([]) == []
    with pytest.raises(ValueError):
        train_rank_fusion_demo(num_pairs=0)
    with pytest.raises(ValueError):
        rank_fusion_pair_accuracy(model, [])
