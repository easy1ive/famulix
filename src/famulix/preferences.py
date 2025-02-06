"""Preference learning and calibration measurement.

Extracts preferences from explicit ratings and implicit feedback signals.
Maintains a versioned style/profile record with confidence decay. Calibration
is measured via Brier score and reliability bins against planted preference
distributions in the synthetic evaluation harness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

FeedbackSignal = Literal["up", "down", "skip", "accept", "decline", "edit"]


@dataclass
class PreferenceEntry:
    """A single preference observation."""

    pref_key: str
    value: str
    signal: FeedbackSignal
    timestamp_s: int
    confidence: float  # 0.0..1.0
    source: str = "unknown"


@dataclass
class PreferenceProfile:
    """Versioned profile of learned preferences.

    Each key maps to a dict of value -> weighted count. The dominant value
    for a key is the one with the highest weighted score.
    """

    version: int = 1
    entries: list[PreferenceEntry] = field(default_factory=list)
    decay_half_life_s: float = 86400 * 30  # 30-day half-life

    def add_feedback(
        self,
        pref_key: str,
        value: str,
        signal: FeedbackSignal,
        timestamp_s: int,
        confidence: float = 0.5,
        source: str = "unknown",
    ) -> None:
        self.entries.append(
            PreferenceEntry(
                pref_key=pref_key,
                value=value,
                signal=signal,
                timestamp_s=timestamp_s,
                confidence=confidence,
                source=source,
            )
        )
        self.version += 1

    def current_preferences(
        self,
        now_s: int,
        *,
        min_confidence: float = 0.2,
    ) -> dict[str, tuple[str, float]]:
        """Compute current dominant preference per key.

        Returns {key: (value, confidence)} where confidence is in [0, 1].
        Only keys with confidence >= min_confidence are returned.
        """
        weights: dict[str, dict[str, float]] = {}
        for entry in self.entries:
            age = max(now_s - entry.timestamp_s, 0)
            decay = float(np.exp(-age * np.log(2) / self.decay_half_life_s))
            # Sign: up/accept/edit = +1, down/decline = -1, skip = +0.1 (weak)
            sign = {
                "up": 1.0,
                "accept": 1.0,
                "edit": 0.8,
                "skip": 0.1,
                "down": -1.0,
                "decline": -1.0,
            }[entry.signal]
            w = entry.confidence * decay * sign
            weights.setdefault(entry.pref_key, {})
            weights[entry.pref_key][entry.value] = weights[entry.pref_key].get(entry.value, 0.0) + w

        result: dict[str, tuple[str, float]] = {}
        for key, value_weights in weights.items():
            best_value = max(value_weights, key=lambda v: value_weights[v])
            raw_conf = value_weights[best_value]
            # Normalize to [0, 1] via tanh-like squashing
            conf = round(float(np.tanh(max(raw_conf, 0.0))), 6)
            if conf >= min_confidence:
                result[key] = (best_value, conf)
        return result

    def preference_keys(self) -> set[str]:
        return {e.pref_key for e in self.entries}


def brier_score(
    predictions: list[float],
    outcomes: list[int],
) -> float:
    """Compute Brier score: mean squared error of probabilistic predictions.

    Lower is better. Range [0, 1]. predictions in [0, 1], outcomes in {0, 1}.
    """
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have same length")
    if not predictions:
        return 0.0
    p = np.array(predictions, dtype=np.float64)
    o = np.array(outcomes, dtype=np.float64)
    return round(float(np.mean((p - o) ** 2)), 6)


def reliability_bins(
    predictions: list[float],
    outcomes: list[int],
    n_bins: int = 10,
) -> list[dict[str, float]]:
    """Compute reliability diagram bins for calibration analysis.

    Each bin has avg_predicted (mean predicted prob) and avg_observed
    (fraction of positive outcomes). Perfect calibration: avg_predicted ==
    avg_observed in every bin.
    """
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have same length")
    p = np.array(predictions, dtype=np.float64)
    o = np.array(outcomes, dtype=np.float64)
    bins: list[dict[str, float]] = []
    for i in range(n_bins):
        lo = i / n_bins
        hi = (i + 1) / n_bins
        mask = (p >= lo) & (p < hi) if i < n_bins - 1 else (p >= lo) & (p <= hi)
        count = int(mask.sum())
        if count == 0:
            bins.append(
                {"lower": lo, "upper": hi, "count": 0.0, "avg_predicted": 0.0, "avg_observed": 0.0}
            )
        else:
            bins.append(
                {
                    "lower": lo,
                    "upper": hi,
                    "count": float(count),
                    "avg_predicted": round(float(p[mask].mean()), 6),
                    "avg_observed": round(float(o[mask].mean()), 6),
                }
            )
    return bins


def calibration_error(
    predictions: list[float],
    outcomes: list[int],
    n_bins: int = 10,
) -> float:
    """Expected calibration error (ECE): weighted average |pred - obs| across bins."""
    bins = reliability_bins(predictions, outcomes, n_bins)
    total = sum(b["count"] for b in bins)
    if total == 0:
        return 0.0
    ece = sum(b["count"] * abs(b["avg_predicted"] - b["avg_observed"]) for b in bins) / total
    return round(ece, 6)
