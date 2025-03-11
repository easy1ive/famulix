"""Optional PyTorch salience scorer.

A small MLP that learns to rank memory nodes by salience, trained on
synthetic data. The NumPy baseline is always available; this module is
an optional extra that requires the `torch` extra dependency.

Marked tests skip cleanly when torch is not installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from famulix.memory_graph import MemoryGraph, MemoryNode

if TYPE_CHECKING:
    import torch  # noqa: F401

try:
    import torch
    from torch import nn

    _TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TORCH_AVAILABLE = False


@dataclass(frozen=True)
class TorchSalienceConfig:
    """Configuration for the torch salience MLP."""

    input_dim: int = 10
    hidden_dim: int = 32
    num_layers: int = 2
    learning_rate: float = 0.01
    epochs: int = 50
    seed: int = 42


def is_torch_available() -> bool:
    """Return True if the torch extra is installed."""
    return _TORCH_AVAILABLE


def _extract_features(node: MemoryNode, now_s: int, freq: float = 1.0) -> list[float]:
    """Extract feature vector for a memory node.

    Features (10-dim):
    0. recency: exponential decay of age
    1. frequency: access/mention count (normalized)
    2. title length (normalized)
    3. body length (normalized)
    4. has goal linkage (binary)
    5. is pinned (binary)
    6. has commitment language (binary)
    7. kind is fact (binary)
    8. kind is episode (binary)
    9. kind is reminder (binary)
    """
    import math

    age_s = max(now_s - node.created_at_s, 0)
    half_life = 86400 * 3
    recency = math.exp(-age_s * math.log(2) / half_life) if age_s > 0 else 1.0

    title_len = min(len(node.title) / 100.0, 1.0)
    body_len = min(len(node.body) / 500.0, 1.0)

    is_goal = node.kind == "goal"
    is_pinned = node.metadata.get("pinned") == "true"

    commitment_words = {"must", "should", "need to", "have to", "deadline", "urgent"}
    text_lower = (node.title + " " + node.body).lower()
    has_commitment = any(w in text_lower for w in commitment_words)

    is_fact = 1.0 if node.kind == "fact" else 0.0
    is_episode = 1.0 if node.kind == "episode" else 0.0
    is_reminder = 1.0 if node.kind == "reminder" else 0.0

    return [
        round(recency, 6),
        round(min(freq, 1.0), 6),
        round(title_len, 6),
        round(body_len, 6),
        1.0 if is_goal else 0.0,
        1.0 if is_pinned else 0.0,
        1.0 if has_commitment else 0.0,
        is_fact,
        is_episode,
        is_reminder,
    ]


class SalienceMLP:
    """A small MLP for salience scoring.

    Compared honestly against the NumPy baseline in evaluation tests.
    Marked model/slow since training runs on every test invocation.
    """

    def __init__(self, config: TorchSalienceConfig | None = None) -> None:
        if not _TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available. Install with: pip install famulix[torch]")
        self.config = config or TorchSalienceConfig()
        torch.manual_seed(self.config.seed)

        layers: list[nn.Module] = []
        prev_dim = self.config.input_dim
        for _ in range(self.config.num_layers - 1):
            layers.append(nn.Linear(prev_dim, self.config.hidden_dim))
            layers.append(nn.ReLU())
            prev_dim = self.config.hidden_dim
        layers.append(nn.Linear(prev_dim, 1))
        layers.append(nn.Sigmoid())
        self.model = nn.Sequential(*layers)

    def score_node(self, node: MemoryNode, now_s: int, freq: float = 1.0) -> float:
        """Score a single node."""
        features = _extract_features(node, now_s, freq)
        x = torch.tensor(features, dtype=torch.float32)
        with torch.no_grad():
            score = self.model(x).item()
        return round(score, 6)

    def score_all(self, graph: MemoryGraph, now_s: int) -> dict[str, float]:
        """Score all active nodes in a graph."""
        scores: dict[str, float] = {}
        for node in graph.all_nodes():
            if not node.is_active:
                continue
            scores[node.node_id] = self.score_node(node, now_s)
        return scores

    def train_on_graphs(
        self,
        graphs: list[MemoryGraph],
        target_scores: list[dict[str, float]],
        now_s: int,
    ) -> list[float]:
        """Train the MLP on graph data. Returns per-epoch losses.

        Targets are ground-truth salience scores (e.g. from the NumPy baseline
        or from planted importance labels). Shows real loss decrease.
        """
        if len(graphs) != len(target_scores):
            raise ValueError("graphs and target_scores must have the same length")

        # Build training data
        features_list: list[list[float]] = []
        targets_list: list[float] = []

        for graph, targets in zip(graphs, target_scores, strict=False):
            for node in graph.all_nodes():
                if not node.is_active:
                    continue
                if node.node_id not in targets:
                    continue
                freq = 1.0  # simplified
                features_list.append(_extract_features(node, now_s, freq))
                targets_list.append(targets[node.node_id])

        if not features_list:
            return []

        x_tensor = torch.tensor(features_list, dtype=torch.float32)
        y_tensor = torch.tensor(targets_list, dtype=torch.float32).unsqueeze(1)

        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.config.learning_rate)
        criterion = nn.MSELoss()

        losses: list[float] = []
        for _epoch in range(self.config.epochs):
            self.model.train()
            optimizer.zero_grad()
            preds = self.model(x_tensor)
            loss = criterion(preds, y_tensor)
            loss.backward()
            optimizer.step()
            losses.append(round(loss.item(), 6))

        return losses


def train_demo_synthetic(
    num_nodes: int = 50,
    seed: int = 42,
    config: TorchSalienceConfig | None = None,
) -> tuple[SalienceMLP, list[float]]:
    """Train a demo model on fully synthetic data.

    Returns the trained model and per-epoch losses.
    Demonstrates real loss decrease on deterministic synthetic data.
    """
    import random

    rng = random.Random(seed)
    graph = MemoryGraph()
    targets: dict[str, float] = {}

    kinds = ["fact", "episode", "reminder", "goal", "entity"]
    for i in range(num_nodes):
        kind = kinds[rng.randint(0, len(kinds) - 1)]
        title = f"node {i}: " + " ".join(
            rng.choice(["meeting", "deadline", "idea", "note", "reminder", "goal", "task"])
            for _ in range(3)
        )
        body = (
            "this is a "
            + " ".join(rng.choice(["very", "somewhat", "moderately", "highly"]) for _ in range(2))
            + " important "
            + kind
        )
        created_at_s = rng.randint(0, 86400 * 30)
        metadata: dict[str, str] = {}
        if rng.random() < 0.1:
            metadata["pinned"] = "true"
        node = MemoryNode.create(
            kind=kind,  # type: ignore[arg-type]
            title=title,
            body=body,
            created_at_s=created_at_s,
            metadata=metadata,
        )
        graph.add_node(node)
        # Target: recency + commitment + pinning heuristic
        age = max(86400 * 30 - created_at_s, 0)
        import math

        recency = math.exp(-age * math.log(2) / (86400 * 3))
        commitment = 0.3 if any(w in body for w in ["must", "deadline", "urgent"]) else 0.0
        pinned = 0.2 if metadata.get("pinned") == "true" else 0.0
        target = min(recency * 0.5 + commitment + pinned, 1.0)
        targets[node.node_id] = round(target, 6)

    model = SalienceMLP(config)
    now_s = 86400 * 30
    losses = model.train_on_graphs([graph], [targets], now_s)
    return model, losses
