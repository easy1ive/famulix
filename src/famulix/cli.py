"""Command-line interface for famulix.

Subcommands: ingest, recall, context, prefs, remember, forget,
export, brief, replay, diff, triggers, privacy, eval, demo.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="famulix",
        description="famulix — offline personal-agent framework",
    )
    parser.add_argument("--version", action="store_true", help="print version")
    sub = parser.add_subparsers(dest="command")

    # demo
    p_demo = sub.add_parser("demo", help="run a full seeded persona day offline")
    p_demo.add_argument("--persona", default="alex", help="persona id (default: alex)")
    p_demo.add_argument("--seed", type=int, default=42, help="random seed (default: 42)")
    p_demo.add_argument("--days", type=int, default=14, help="days of history (default: 14)")
    p_demo.add_argument("--json", action="store_true", help="output as JSON")

    # eval
    p_eval = sub.add_parser("eval", help="run evaluation on a synthetic persona")
    p_eval.add_argument("--persona", default="alex", help="persona id")
    p_eval.add_argument("--seed", type=int, default=0, help="random seed")
    p_eval.add_argument("--days", type=int, default=90, help="days of history")
    p_eval.add_argument("--budget", type=int, default=500, help="token budget")
    p_eval.add_argument("--json", action="store_true", help="output as JSON")

    # recall
    p_recall = sub.add_parser("recall", help="search memory graph for a query")
    p_recall.add_argument("query", nargs="?", default="", help="search query")
    p_recall.add_argument("--persona", default="alex", help="persona id for demo graph")
    p_recall.add_argument("--seed", type=int, default=0, help="seed for demo graph")
    p_recall.add_argument("--days", type=int, default=30, help="days for demo graph")
    p_recall.add_argument("-k", type=int, default=10, help="top-k results")

    # brief
    p_brief = sub.add_parser("brief", help="generate a daily briefing")
    p_brief.add_argument("--persona", default="alex", help="persona id")
    p_brief.add_argument("--seed", type=int, default=0, help="random seed")
    p_brief.add_argument("--days", type=int, default=30, help="days of history")
    p_brief.add_argument("--date", help="date string (default: last day)")
    p_brief.add_argument("--budget", type=int, default=500, help="token budget")
    p_brief.add_argument("--output", help="output file (default: stdout)")
    p_brief.add_argument(
        "--format", choices=["markdown", "html"], default="markdown", help="output format"
    )

    # context
    p_ctx = sub.add_parser("context", help="assemble budgeted context for a query")
    p_ctx.add_argument("query", nargs="?", default="", help="context query")
    p_ctx.add_argument("--persona", default="alex", help="persona id")
    p_ctx.add_argument("--seed", type=int, default=0, help="seed")
    p_ctx.add_argument("--days", type=int, default=30, help="days of history")
    p_ctx.add_argument("--budget", type=int, default=300, help="token budget")

    # prefs
    p_prefs = sub.add_parser("prefs", help="view learned preferences")
    p_prefs.add_argument("--persona", default="alex", help="persona id")
    p_prefs.add_argument("--seed", type=int, default=0, help="seed")
    p_prefs.add_argument("--days", type=int, default=30, help="days of history")

    # remember
    p_rem = sub.add_parser("remember", help="add a fact to memory")
    p_rem.add_argument("title", help="fact title")
    p_rem.add_argument("body", help="fact body")

    # forget
    p_forget = sub.add_parser("forget", help="remove a memory by id")
    p_forget.add_argument("memory_id", help="memory id to delete")

    # ingest
    p_ingest = sub.add_parser("ingest", help="ingest events from JSONL")
    p_ingest.add_argument("path", help="path to JSONL event file")

    # export
    p_export = sub.add_parser("export", help="export memory graph")
    p_export.add_argument("--format", choices=["json", "jsonl"], default="json")
    p_export.add_argument("--output", help="output file (default: stdout)")

    # triggers
    p_trig = sub.add_parser("triggers", help="list proactive triggers")
    p_trig.add_argument("--persona", default="alex", help="persona id")
    p_trig.add_argument("--seed", type=int, default=0, help="seed")
    p_trig.add_argument("--days", type=int, default=30, help="days of history")

    # privacy
    p_priv = sub.add_parser("privacy", help="privacy and redaction tools")
    p_priv.add_argument("text", nargs="?", default="", help="text to scan/redact")
    p_priv.add_argument("--mode", choices=["detect", "redact"], default="detect")

    # replay
    p_replay = sub.add_parser("replay", help="replay a recorded session")
    p_replay.add_argument("path", help="path to session JSONL")

    # diff
    p_diff = sub.add_parser("diff", help="diff two session recordings")
    p_diff.add_argument("path_a", help="first session path")
    p_diff.add_argument("path_b", help="second session path")

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
    handlers: dict[str, object] = {
        "demo": cmd_demo,
        "eval": cmd_eval,
        "recall": cmd_recall,
        "brief": cmd_brief,
        "context": cmd_context,
        "prefs": cmd_prefs,
        "remember": cmd_remember,
        "forget": cmd_forget,
        "ingest": cmd_ingest,
        "export": cmd_export,
        "triggers": cmd_triggers,
        "privacy": cmd_privacy,
        "replay": cmd_replay,
        "diff": cmd_diff,
    }
    handler = handlers.get(args.command)
    if handler is None:
        print(f"famulix {args.command}: not yet implemented", file=sys.stderr)
        return 1
    return handler(args)  # type: ignore[operator]


def _build_demo_graph(persona: str, seed: int, days: int):
    """Build a demo graph from synthetic history."""
    from famulix.consolidation import consolidate_graph
    from famulix.encoding import encode_events_to_graph
    from famulix.factory import generate_history

    events, _manifest = generate_history(persona_id=persona, seed=seed, days=days)
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)
    now_s = events[-1].timestamp_s + 3600 if events else 0
    return graph, now_s


def cmd_demo(args: argparse.Namespace) -> int:
    """Run a full seeded persona day offline."""
    from famulix.evaluation import run_full_evaluation

    scorecard = run_full_evaluation(
        persona_id=args.persona,
        seed=args.seed,
        days=args.days,
    )
    d = scorecard.to_dict()
    if getattr(args, "json", False):
        print(json.dumps(d, indent=2, sort_keys=True))
    else:
        print(f"famulix demo — persona={d['persona_id']} seed={d['seed']} days={d['days']}")
        print(f"  Planted facts:      {d['total_planted_facts']}")
        print(f"  Contradictions:     {d['total_contradiction_pairs']}")
        print(f"  Recall@5:           {d['recall_at_k']['@5']:.4f}")
        print(f"  Precision@5:        {d['precision_at_k']['@5']:.4f}")
        print(f"  Contradiction acc:  {d['contradiction_accuracy']:.4f}")
        print(f"  Citation coverage:  {d['citation_coverage']:.4f}")
        print(f"  Preference Brier:   {d['preference_brier_score']:.4f}")
        print(f"  Replay determinism: {d['replay_deterministic']}")
        print(f"  Budget adherence:   {d['budget_adherence']}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    """Run evaluation and print the scorecard."""
    from famulix.evaluation import run_full_evaluation

    scorecard = run_full_evaluation(
        persona_id=args.persona,
        seed=args.seed,
        days=args.days,
        budget_tokens=args.budget,
    )
    d = scorecard.to_dict()
    if getattr(args, "json", False):
        print(json.dumps(d, indent=2, sort_keys=True))
    else:
        print(f"Evaluation: {d['persona_id']} (seed={d['seed']}, days={d['days']})")
        for key, val in sorted(d.items()):
            if key in ("persona_id", "seed", "days", "slices"):
                continue
            print(f"  {key}: {val}")
    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    """Run a recall query against a demo graph."""
    from famulix.retrieval import BM25Index, hybrid_score

    graph, now_s = _build_demo_graph(args.persona, args.seed, args.days)
    idx = BM25Index()
    for node in graph.all_nodes():
        if node.is_active:
            idx.add_node(node)
    query = args.query or "important facts"
    results = hybrid_score(query, graph=graph, index=idx, now_s=now_s)
    print(f"Top {args.k} results for: {query}")
    for i, r in enumerate(results[: args.k]):
        node = graph.get_node(r.node_id)
        if node is None:
            continue
        print(f"  {i + 1}. [{node.kind}] {node.title} (score={r.score:.4f})")
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    """Generate a briefing from synthetic history."""
    from famulix.briefing import build_briefing, render_briefing_html, render_briefing_markdown

    graph, now_s = _build_demo_graph(args.persona, args.seed, args.days)
    date_str = args.date or _default_date(graph, args.persona, args.seed, args.days)
    briefing = build_briefing(
        graph,
        date_str=date_str,
        now_s=now_s,
        budget_tokens=args.budget,
        seed=args.seed,
    )
    if args.format == "html":
        output = render_briefing_html(briefing, graph=graph)
    else:
        output = render_briefing_markdown(briefing)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Briefing written to {args.output}")
    else:
        print(output)
    return 0


def _default_date(graph, persona: str, seed: int, days: int) -> str:
    """Compute the last day of the synthetic history."""
    from famulix.factory import generate_history

    _events, manifest = generate_history(persona_id=persona, seed=seed, days=days)
    return manifest.end_date


def cmd_context(args: argparse.Namespace) -> int:
    """Assemble budgeted context for a query."""
    from famulix.context import ContextItem, assemble_context, estimate_tokens
    from famulix.retrieval import BM25Index, hybrid_score

    graph, now_s = _build_demo_graph(args.persona, args.seed, args.days)
    idx = BM25Index()
    for node in graph.all_nodes():
        if node.is_active:
            idx.add_node(node)
    query = args.query or "context assembly test"
    results = hybrid_score(query, graph=graph, index=idx, now_s=now_s)
    context_items: list[ContextItem] = []
    for r in results[:20]:
        node = graph.get_node(r.node_id)
        if node is None:
            continue
        text = f"{node.title}: {node.body}"
        context_items.append(
            ContextItem(
                item_id=node.node_id,
                token_estimate=estimate_tokens(text),
                value=r.score,
                payload=text,
            )
        )
    assembled = assemble_context(context_items, budget=args.budget)
    print(f"Assembled context (budget={args.budget} tokens):")
    total = 0
    for ci in assembled.items:
        total += ci.token_estimate
        print(f"  [{ci.token_estimate:3d} tok, val={ci.value:.3f}] {ci.payload[:60]}")
    print(f"Total: {total} tokens / {len(assembled.items)} items")
    return 0


def cmd_prefs(args: argparse.Namespace) -> int:
    """Show learned preferences from synthetic history."""
    from famulix.factory import generate_history_with_truth
    from famulix.preferences import PreferenceProfile

    _events, _manifest, truth = generate_history_with_truth(
        persona_id=args.persona, seed=args.seed, days=args.days
    )
    profile = PreferenceProfile()
    for idx, sig in enumerate(truth["preference_signals"]):
        profile.add_feedback(
            pref_key=sig["key"],
            value=sig["value"],
            signal=sig["rating"],  # type: ignore[arg-type]
            timestamp_s=idx * 3600,
            confidence=0.6,
            source="synthetic",
        )
    now_s = len(truth["preference_signals"]) * 3600
    prefs = profile.current_preferences(now_s)
    print(f"Learned preferences ({len(prefs)} keys):")
    for key, (value, conf) in sorted(prefs.items()):
        print(f"  {key}: {value} (confidence: {conf:.3f})")
    return 0


def cmd_remember(args: argparse.Namespace) -> int:
    """Add a fact and print its memory id."""
    from famulix.memory_graph import MemoryNode

    node = MemoryNode.create(kind="fact", title=args.title, body=args.body)
    print(f"Memory id: {node.node_id}")
    print(f"Title: {node.title}")
    print(f"Body: {node.body}")
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    """Forget a memory (demo of deletion semantics)."""
    print(f"Marked {args.memory_id} for deletion (tombstone mode).")
    print("Note: in a real store, this cascades across indexes and projections.")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """Ingest events from a JSONL file."""
    print(f"Would ingest events from: {args.path}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export the demo memory graph."""
    graph, _now = _build_demo_graph("alex", 0, 7)
    nodes = [
        {"id": n.node_id, "kind": n.kind, "title": n.title, "body": n.body}
        for n in graph.all_nodes()
    ]
    if args.format == "jsonl":
        for node in nodes:
            print(json.dumps(node, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(nodes, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_triggers(args: argparse.Namespace) -> int:
    """List proactive triggers for a demo graph."""
    from famulix.triggers import generate_triggers

    graph, now_s = _build_demo_graph(args.persona, args.seed, args.days)
    triggers = generate_triggers(graph, now_s=now_s)
    print(f"Generated {len(triggers)} triggers:")
    for t in triggers[:20]:
        print(f"  [{t.kind}] {t.title} (score={t.score:.3f})")
    return 0


def cmd_privacy(args: argparse.Namespace) -> int:
    """Detect or redact PII in text."""
    from famulix.privacy import detect_pii, redact_text

    text = args.text or "Contact me at test@example.com or 555-123-4567."
    if args.mode == "detect":
        findings = detect_pii(text)
        print(f"Found {len(findings)} PII items:")
        for f in findings:
            print(f"  {f.pii_type}: {f.text} (pos {f.start}-{f.end})")
    else:
        redacted = redact_text(text)
        print(f"Original: {text}")
        print(f"Redacted: {redacted}")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    """Replay a session recording (placeholder)."""
    print(f"Would replay session from: {args.path}")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    """Diff two sessions (placeholder)."""
    print(f"Would diff: {args.path_a} vs {args.path_b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
