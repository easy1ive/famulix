"""Learn briefing style from a small synthetic feedback stream.

Run: python examples/03_preference_loop.py
"""

from __future__ import annotations

from famulix.personalization import apply_preferences, counterfactual_compare
from famulix.preferences import PreferenceProfile, brier_score


def main() -> int:
    profile = PreferenceProfile()
    signals = [("concise", "up"), ("concise", "up"), ("detailed", "down")]
    for index, (value, signal) in enumerate(signals):
        profile.add_feedback("tone", value, signal, timestamp_s=1_800_000_000 + index * 60)
    now = 1_800_000_300
    style = apply_preferences(profile, now_s=now)
    print("Synthetic preference feedback (three signals)")
    print(f"Selected tone: {style.tone}")
    for explanation in style.explain():
        print(f"  {explanation}")
    baseline = PreferenceProfile()
    comparison = counterfactual_compare(baseline, profile, now_s=now)
    observed = [1, 1, 0]
    predicted = [0.75, 0.75, 0.25]
    print(f"Cold-start vs learned: {comparison['tone']}")
    print(f"Illustrative synthetic Brier score: {brier_score(predicted, observed):.4f}")
    print("Scores describe only this constructed feedback stream.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
