"""Command-line interface for famulix.

Subcommands: ingest, recall, context, prefs, remember, forget,
export, brief, replay, diff, triggers, privacy, eval, demo.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="famulix",
        description="famulix — offline personal-agent framework",
    )
    parser.add_argument("--version", action="store_true", help="print version")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("demo", help="run a full seeded persona day offline")
    sub.add_parser("recall", help="search memory graph for a query")
    sub.add_parser("brief", help="generate a daily briefing")
    sub.add_parser("eval", help="run evaluation on a synthetic persona")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        from famulix import __version__

        print(__version__)
        return 0
    if args.command is None:
        parser.print_help()
        return 0
    return _dispatch(args)


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "demo":
        return cmd_demo(args)
    if args.command == "recall":
        return cmd_recall(args)
    if args.command == "brief":
        return cmd_brief(args)
    if args.command == "eval":
        return cmd_eval(args)
    print(f"famulix {args.command}: not yet implemented", file=sys.stderr)
    return 1


def cmd_demo(args: argparse.Namespace) -> int:
    """Run a full seeded persona day offline."""
    from famulix.evaluation import run_full_evaluation

    print("famulix demo — running synthetic persona evaluation...")
    scorecard = run_full_evaluation(persona_id="alex", seed=42, days=14)
    d = scorecard.to_dict()
    print(f"Persona: {d['persona_id']} (seed={d['seed']}, days={d['days']})")
    print(f"Planted facts: {d['total_planted_facts']}")
    print(f"Contradiction pairs: {d['total_contradiction_pairs']}")
    print(f"Recall@5: {d['recall_at_k']['@5']:.4f}")
    print(f"Precision@5: {d['precision_at_k']['@5']:.4f}")
    print(f"Contradiction accuracy: {d['contradiction_accuracy']:.4f}")
    print(f"Citation coverage: {d['citation_coverage']:.4f}")
    print(f"Preference Brier: {d['preference_brier_score']:.4f}")
    print(f"Replay deterministic: {d['replay_deterministic']}")
    print(f"Budget adherence: {d['budget_adherence']}")
    print("Done.")
    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    """Recall command placeholder."""
    print("recall: use famulix recall <query> [--graph PATH]")
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    """Brief command placeholder."""
    print("brief: use famulix brief [--date YYYY-MM-DD] [--output PATH]")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    """Eval command placeholder."""
    print("eval: use famulix eval [--persona ID] [--seed N] [--days N]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
