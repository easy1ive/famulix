#!/usr/bin/env python3
"""Example: Generating reports from evaluation and preferences.

This example demonstrates how to generate human-readable reports from
evaluation scorecards and preference profiles, including the honest
limitations sections that are automatically generated.
"""

from famulix.evaluation import format_evaluation_report, run_full_evaluation
from famulix.factory import generate_history_with_truth
from famulix.preferences import PreferenceProfile


def main():
    print("=" * 70)
    print("famulix Reporting Example")
    print("=" * 70)
    print()

    # Generate a preference profile report
    print("Generating preference profile report...")
    _events, _manifest, truth = generate_history_with_truth(persona_id="alex", seed=42, days=30)
    profile = PreferenceProfile()
    for idx, sig in enumerate(truth["preference_signals"]):
        profile.add_feedback(
            pref_key=sig["key"],
            value=sig["value"],
            signal=sig["rating"],
            timestamp_s=idx * 3600,
            confidence=0.6,
            source="synthetic",
        )
    now_s = len(truth["preference_signals"]) * 3600
    pref_report = profile.generate_report(now_s)
    print(pref_report)
    print()

    # Run a full evaluation and generate a report
    print("Running full evaluation...")
    scorecard = run_full_evaluation(
        persona_id="alex",
        seed=42,
        days=14,
        budget_tokens=500,
    )
    scorecard_dict = scorecard.to_dict()
    eval_report = format_evaluation_report(scorecard_dict, include_details=True)
    print(eval_report)

    print("=" * 70)
    print("Reports generated successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
