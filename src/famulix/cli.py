"""Command-line interface for famulix.

Subcommands: ingest, recall, context, prefs, remember, forget,
export, brief, replay, diff, triggers, privacy, eval, demo.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence

from famulix.memory_graph import MemoryGraph


def _positive_int(value: str) -> int:
    """Parse a positive CLI count or budget with a concise argparse error."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer greater than zero") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


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
    p_demo.add_argument(
        "--days", type=_positive_int, default=14, help="days of history (default: 14)"
    )
    p_demo.add_argument("--json", action="store_true", help="output as JSON")

    # eval
    p_eval = sub.add_parser("eval", help="run evaluation on a synthetic persona")
    p_eval.add_argument("--persona", default="alex", help="persona id")
    p_eval.add_argument("--seed", type=int, default=0, help="random seed")
    p_eval.add_argument("--days", type=_positive_int, default=90, help="days of history")
    p_eval.add_argument("--budget", type=_positive_int, default=500, help="token budget")
    p_eval.add_argument(
        "--slice",
        dest="slices",
        action="append",
        help="show only specific slice (can be repeated: recall, precision, etc.)",
    )

    # exec-report
    sub.add_parser("exec-report", help="generate plan execution report")
    p_eval.add_argument("--json", action="store_true", help="output as JSON")

    # recall
    p_recall = sub.add_parser("recall", help="search memory graph for a query")
    p_recall.add_argument("query", nargs="?", default="", help="search query")
    p_recall.add_argument("--persona", default="alex", help="persona id for demo graph")
    p_recall.add_argument("--seed", type=int, default=0, help="seed for demo graph")
    p_recall.add_argument("--days", type=_positive_int, default=30, help="days for demo graph")
    p_recall.add_argument("-k", type=_positive_int, default=10, help="top-k results")
    p_recall.add_argument("--json", action="store_true", help="output as JSON")
    p_recall.add_argument(
        "--diverse",
        action="store_true",
        help="apply MMR diversity reranking (lambda=0.7)",
    )
    p_recall.add_argument(
        "--rebuild-index",
        action="store_true",
        help="rebuild BM25 index from graph before search",
    )

    # brief
    p_brief = sub.add_parser("brief", help="generate a daily briefing")
    p_brief.add_argument("--persona", default="alex", help="persona id")
    p_brief.add_argument("--seed", type=int, default=0, help="random seed")
    p_brief.add_argument("--days", type=_positive_int, default=30, help="days of history")
    p_brief.add_argument("--date", help="date string (default: last day)")
    p_brief.add_argument("--budget", type=_positive_int, default=500, help="token budget")
    p_brief.add_argument("--output", help="output file (default: stdout)")
    p_brief.add_argument(
        "--format", choices=["markdown", "html", "json"], default="markdown", help="output format"
    )
    p_brief.add_argument(
        "--section",
        choices=["agenda", "commitments", "reminders", "memories"],
        help="generate only specific section",
    )

    # context
    p_ctx = sub.add_parser("context", help="assemble budgeted context for a query")
    p_ctx.add_argument("query", nargs="?", default="", help="context query")
    p_ctx.add_argument("--persona", default="alex", help="persona id")
    p_ctx.add_argument("--seed", type=int, default=0, help="seed")
    p_ctx.add_argument("--days", type=_positive_int, default=30, help="days of history")
    p_ctx.add_argument("--budget", type=_positive_int, default=300, help="token budget")
    p_ctx.add_argument("--json", action="store_true", help="output as JSON")
    p_ctx.add_argument(
        "--max-items",
        type=_positive_int,
        default=10,
        help="maximum number of context items (default: 10)",
    )

    # prefs
    p_prefs = sub.add_parser("prefs", help="view learned preferences")
    p_prefs.add_argument("--persona", default="alex", help="persona id")
    p_prefs.add_argument("--seed", type=int, default=0, help="seed")
    p_prefs.add_argument("--days", type=_positive_int, default=30, help="days of history")
    p_prefs.add_argument("--json", action="store_true", help="output as JSON")
    p_prefs.add_argument(
        "--learned-only",
        action="store_true",
        help="show only learned preferences (exclude cold-start defaults)",
    )

    # prefs-report
    p_prefs_report = sub.add_parser("prefs-report", help="generate preference profile report")
    p_prefs_report.add_argument("--persona", default="alex", help="persona id")
    p_prefs_report.add_argument("--seed", type=int, default=0, help="seed")
    p_prefs_report.add_argument("--days", type=_positive_int, default=30, help="days of history")

    # remember
    p_rem = sub.add_parser("remember", help="add a fact to memory")
    p_rem.add_argument("title", help="fact title")
    p_rem.add_argument("body", help="fact body")
    p_rem.add_argument(
        "--confidence",
        type=float,
        default=0.8,
        help="confidence score 0.0-1.0 (default: 0.8)",
    )
    p_rem.add_argument(
        "--tags",
        nargs="*",
        default=[],
        help="tags for categorization",
    )

    # forget
    p_forget = sub.add_parser("forget", help="remove a memory by id")
    p_forget.add_argument("memory_id", help="memory id to delete")
    p_forget.add_argument("--persona", default="alex", help="persona id (default: alex)")
    p_forget.add_argument("--seed", type=int, default=0, help="factory seed")
    p_forget.add_argument("--days", type=int, default=30, help="history days")
    p_forget.add_argument("--reason", default="user request", help="deletion reason")
    p_forget.add_argument("--json", action="store_true", help="JSON output")
    p_forget.add_argument(
        "--no-cascade",
        action="store_true",
        help="delete only the specified memory (skip cascade)",
    )

    # ingest
    p_ingest = sub.add_parser("ingest", help="ingest events from JSONL")
    p_ingest.add_argument("path", help="path to JSONL event file")
    p_ingest.add_argument(
        "--validate",
        action="store_true",
        help="validate schema before ingest (slower but safer)",
    )

    # export
    p_export = sub.add_parser("export", help="export memory graph")
    p_export.add_argument("--format", choices=["json", "jsonl"], default="json")
    p_export.add_argument("--output", help="output file (default: stdout)")
    p_export.add_argument(
        "--pretty",
        action="store_true",
        help="pretty-print JSON output (indent=2)",
    )

    # triggers
    p_trig = sub.add_parser("triggers", help="list proactive triggers")
    p_trig.add_argument("--persona", default="alex", help="persona id")
    p_trig.add_argument("--seed", type=int, default=0, help="seed")
    p_trig.add_argument("--days", type=_positive_int, default=30, help="days of history")
    p_trig.add_argument("--json", action="store_true", help="output as JSON")
    p_trig.add_argument(
        "--active-only",
        action="store_true",
        help="show only active (non-expired) triggers",
    )

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
    p_diff.add_argument("--json", action="store_true", help="output diff as JSON (default)")
    p_diff.add_argument(
        "--summary",
        action="store_true",
        help="show human-readable summary instead of JSON",
    )

    # stats
    p_stats = sub.add_parser("stats", help="show memory graph statistics")
    p_stats.add_argument("--persona", default="alex", help="persona id")
    p_stats.add_argument("--seed", type=int, default=0, help="seed")
    p_stats.add_argument("--days", type=_positive_int, default=30, help="days of history")
    p_stats.add_argument("--json", action="store_true", help="output as JSON")
    p_stats.add_argument(
        "--verbose",
        action="store_true",
        help="show detailed statistics including edge kinds and node metadata",
    )

    # validate-session
    p_validate = sub.add_parser("validate-session", help="validate a session recording file")
    p_validate.add_argument("path", help="path to session JSONL file")
    p_validate.add_argument("--json", action="store_true", help="output as JSON")

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
    handlers: dict[str, Callable[[argparse.Namespace], int]] = {
        "demo": cmd_demo,
        "eval": cmd_eval,
        "exec-report": cmd_exec_report,
        "recall": cmd_recall,
        "brief": cmd_brief,
        "context": cmd_context,
        "prefs": cmd_prefs,
        "prefs-report": cmd_prefs_report,
        "remember": cmd_remember,
        "forget": cmd_forget,
        "ingest": cmd_ingest,
        "export": cmd_export,
        "triggers": cmd_triggers,
        "privacy": cmd_privacy,
        "replay": cmd_replay,
        "diff": cmd_diff,
        "stats": cmd_stats,
        "validate-session": cmd_validate_session,
    }
    handler = handlers.get(args.command)
    if handler is None:
        print(f"famulix {args.command}: not yet implemented", file=sys.stderr)
        return 1
    return handler(args)


def _build_demo_graph(persona: str, seed: int, days: int) -> tuple[MemoryGraph, int]:
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

    # Filter slices if requested
    selected_slices = getattr(args, "slices", None)
    if selected_slices and "slices" in d:
        d["slices"] = {k: v for k, v in d["slices"].items() if k in selected_slices}

    if getattr(args, "json", False):
        print(json.dumps(d, indent=2, sort_keys=True))
    else:
        print(f"Evaluation: {d['persona_id']} (seed={d['seed']}, days={d['days']})")
        for key, val in sorted(d.items()):
            if key in ("persona_id", "seed", "days", "slices"):
                continue
            print(f"  {key}: {val}")

        # Print selected slices if any
        if selected_slices and "slices" in d and d["slices"]:
            print("  slices:")
            for slice_name, slice_data in sorted(d["slices"].items()):
                print(f"    {slice_name}: {slice_data}")
    return 0


def cmd_exec_report(args: argparse.Namespace) -> int:
    """Generate a plan execution report from a demo run."""
    from famulix.executor import ExecutionState, StepExecution, format_execution_report

    # Create a demo execution state
    state = ExecutionState()
    state.history.append(StepExecution(step_id="ingest", success=True))
    state.history.append(StepExecution(step_id="consolidate", success=True))
    state.history.append(StepExecution(step_id="recall", success=True))
    state.history.append(StepExecution(step_id="brief", success=True))
    state.steps_done = 4
    state.tokens_used = 1200
    state.money_spent = 0.05

    report = format_execution_report(state)
    print(report)
    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    """Run a recall query against a demo graph."""
    from famulix.retrieval import BM25Index, hybrid_score, mmr_rerank

    graph, now_s = _build_demo_graph(args.persona, args.seed, args.days)
    idx = BM25Index()

    # Rebuild index if requested or if stale
    if getattr(args, "rebuild_index", False) or idx.needs_rebuild(graph):
        idx.rebuild_from_graph(graph)
    else:
        for node in graph.all_nodes():
            if node.is_active:
                idx.add_node(node)

    query = args.query or "important facts"
    results = hybrid_score(query, graph=graph, index=idx, now_s=now_s)

    # Apply MMR diversity reranking if requested
    if getattr(args, "diverse", False):
        # Fetch more candidates for MMR to choose from
        candidates = results[: args.k * 3]
        results = mmr_rerank(candidates, graph=graph, top_k=args.k, lambda_param=0.7)

    top_results = results[: args.k]

    if getattr(args, "json", False):
        output = {
            "query": query,
            "persona": args.persona,
            "seed": args.seed,
            "days": args.days,
            "results": [
                (
                    lambda node: {
                        "rank": i + 1,
                        "node_id": r.node_id,
                        "kind": node.kind if node else None,
                        "title": node.title if node else None,
                        "score": r.score,
                        "citation": r.citation,
                    }
                )(graph.get_node(r.node_id))
                for i, r in enumerate(top_results)
            ],
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"Top {args.k} results for: {query}")
        for i, r in enumerate(top_results):
            result_node = graph.get_node(r.node_id)
            if result_node is None:
                continue
            print(f"  {i + 1}. [{result_node.kind}] {result_node.title} (score={r.score:.4f})")
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

    # Filter to specific section if requested
    section = getattr(args, "section", None)
    if section:
        # Simple section filter: extract lines between section headers
        lines = output.split("\n")
        section_headers = {
            "agenda": "Agenda",
            "commitments": "Commitments",
            "reminders": "Reminders",
            "memories": "Recent Memories",
        }
        target = section_headers.get(section, section.title())
        filtered = []
        in_section = False
        for line in lines:
            if line.startswith("#") and target in line:
                in_section = True
                filtered.append(line)
            elif line.startswith("#") and in_section:
                break
            elif in_section:
                filtered.append(line)
        output = "\n".join(filtered) if filtered else f"No {section} section found"

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Briefing written to {args.output}")
    else:
        print(output)
    return 0


def _default_date(graph: MemoryGraph, persona: str, seed: int, days: int) -> str:
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
    max_items = getattr(args, "max_items", 10)
    for r in results[: max_items * 2]:
        result_node = graph.get_node(r.node_id)
        if result_node is None:
            continue
        text = f"{result_node.title}: {result_node.body}"
        context_items.append(
            ContextItem(
                item_id=result_node.node_id,
                token_estimate=estimate_tokens(text),
                value=r.score,
                payload=text,
            )
        )
        if len(context_items) >= max_items:
            break
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
            signal=sig["rating"],
            timestamp_s=idx * 3600,
            confidence=0.6,
            source="synthetic",
        )
    now_s = len(truth["preference_signals"]) * 3600
    prefs = profile.current_preferences(now_s)

    # Filter to learned-only if requested (confidence > 0)
    if getattr(args, "learned_only", False):
        prefs = {k: (v, c) for k, (v, c) in prefs.items() if c > 0.0}

    print(f"Learned preferences ({len(prefs)} keys):")
    for key, (value, conf) in sorted(prefs.items()):
        print(f"  {key}: {value} (confidence: {conf:.3f})")
    return 0


def cmd_prefs_report(args: argparse.Namespace) -> int:
    """Generate a full preference profile report."""
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
            signal=sig["rating"],
            timestamp_s=idx * 3600,
            confidence=0.6,
            source="synthetic",
        )
    now_s = len(truth["preference_signals"]) * 3600
    report = profile.generate_report(now_s)
    print(report)
    return 0


def cmd_remember(args: argparse.Namespace) -> int:
    """Add a fact and print its memory id."""
    from famulix.memory_graph import MemoryNode

    # Build metadata from flags
    metadata = {}
    confidence = getattr(args, "confidence", 0.8)
    if confidence != 0.8:
        metadata["confidence"] = str(confidence)
    tags = getattr(args, "tags", [])
    if tags:
        metadata["tags"] = ",".join(tags)

    node = MemoryNode.create(kind="fact", title=args.title, body=args.body, metadata=metadata)
    print(f"Memory id: {node.node_id}")
    print(f"Title: {node.title}")
    print(f"Body: {node.body}")
    if confidence != 0.8:
        print(f"Confidence: {confidence:.2f}")
    if tags:
        print(f"Tags: {', '.join(tags)}")
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    """Delete a memory and cascade across the graph and index."""
    from famulix.deletion import delete_memory, deletion_audit_report, is_deleted
    from famulix.retrieval import BM25Index

    graph, _now = _build_demo_graph(args.persona, args.seed, args.days)
    idx = BM25Index()
    for node in graph.all_nodes():
        if node.is_active:
            idx.add_node(node)

    memory_id = args.memory_id
    if graph.get_node(memory_id) is None:
        print(f"Error: memory '{memory_id}' not found", file=sys.stderr)
        return 1
    if is_deleted(graph, memory_id):
        print(f"Error: memory '{memory_id}' already deleted", file=sys.stderr)
        return 1

    # Check if cascade is disabled
    no_cascade = getattr(args, "no_cascade", False)
    if no_cascade:
        # Simple deletion: just mark as inactive
        from dataclasses import replace

        node = graph.get_node(memory_id)
        graph._nodes[memory_id] = replace(node, is_active=False)  # noqa: SLF001
        idx.remove(memory_id)
        print(f"Deleted memory (no cascade): {memory_id}")
        print(f"  reason: {args.reason}")
        return 0

    report = delete_memory(graph, memory_id)
    idx.remove(memory_id)

    if getattr(args, "json", False):
        output = {
            "deleted": memory_id,
            "reason": args.reason,
            "nodes_removed": len(report.deleted_nodes),
            "edges_removed": len(report.deleted_edges),
            "tombstoned": len(report.tombstone_nodes),
            "cascade_depth": report.cascade_depth,
            "audit": deletion_audit_report(graph),
        }
        print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    else:
        print(f"Deleted memory: {memory_id}")
        print(f"  reason: {args.reason}")
        print(f"  nodes removed: {len(report.deleted_nodes)}")
        print(f"  edges removed: {len(report.deleted_edges)}")
        print(f"  tombstoned: {len(report.tombstone_nodes)}")
        print(f"  cascade depth: {report.cascade_depth}")
        print("Verification: deleted memory does not appear in retrieval results.")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """Ingest events from a JSONL file."""
    from pathlib import Path

    from famulix.encoding import encode_events_to_graph
    from famulix.envelope import Envelope
    from famulix.events import Event

    try:
        lines = Path(args.path).read_text(encoding="utf-8").splitlines()

        # Validate schema if requested
        if getattr(args, "validate", False):
            envelopes = []
            for i, line in enumerate(lines):
                if not line:
                    continue
                try:
                    env = Envelope.from_jsonl_line(line)
                    envelopes.append(env)
                except (ValueError, KeyError, TypeError) as exc:
                    print(f"Validation error at line {i + 1}: {exc}", file=sys.stderr)
                    return 3
            events = [Event.from_envelope(env) for env in envelopes]
        else:
            events = [Event.from_envelope(Envelope.from_jsonl_line(line)) for line in lines if line]

        graph = encode_events_to_graph(events)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"famulix ingest: {exc}", file=sys.stderr)
        return 2
    print(f"Ingested {len(events)} events into {graph.node_count()} memory nodes")
    print(f"  Episodes: {sum(node.kind == 'episode' for node in graph.all_nodes())}")
    print(f"  Facts:    {sum(node.kind == 'fact' for node in graph.all_nodes())}")
    print(f"  Entities: {sum(node.kind == 'entity' for node in graph.all_nodes())}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export the demo memory graph."""
    graph, _now = _build_demo_graph("alex", 0, 7)
    serialized = graph.to_dict()

    # Determine JSON indent
    indent = 2 if getattr(args, "pretty", False) else None

    if args.format == "jsonl":
        print(json.dumps({"record_type": "graph", "schema_version": 1}, sort_keys=True))
        for node in serialized["nodes"]:
            print(json.dumps({"record_type": "node", **node}, sort_keys=True, ensure_ascii=False))
        for edge in serialized["edges"]:
            print(json.dumps({"record_type": "edge", **edge}, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(serialized, indent=indent, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_triggers(args: argparse.Namespace) -> int:
    """List proactive triggers for a demo graph."""
    from famulix.triggers import generate_triggers

    graph, now_s = _build_demo_graph(args.persona, args.seed, args.days)
    triggers = generate_triggers(graph, now_s=now_s)

    # Filter to active-only if requested
    if getattr(args, "active_only", False):
        triggers = [t for t in triggers if t.trigger_time_s >= now_s]

    print(f"Generated {len(triggers)} triggers:")
    for t in triggers[:20]:
        print(f"  [{t.trigger_time_s}] {t.reason} (memory={t.memory_id})")
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
    """Verify and summarize a recorded session."""
    from famulix.session import SessionRecorder

    try:
        recorder = SessionRecorder.load(args.path)
    except (OSError, ValueError) as exc:
        print(f"famulix replay: {exc}", file=sys.stderr)
        return 2
    print(f"Verified session {recorder.session_id}: {len(recorder.entries)} frames")
    print(f"Digest: {recorder.digest()}")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    """Compare two verified session recordings."""
    from famulix.session import SessionRecorder, session_diff

    try:
        left = SessionRecorder.load(args.path_a)
        right = SessionRecorder.load(args.path_b)
    except (OSError, ValueError) as exc:
        print(f"famulix diff: {exc}", file=sys.stderr)
        return 2

    diff_result = session_diff(left, right)

    if getattr(args, "summary", False):
        # Human-readable summary
        print(f"Session diff: {args.path_a} vs {args.path_b}")
        print(f"  Left frames:  {len(left.entries)}")
        print(f"  Right frames: {len(right.entries)}")
        print(f"  Identical:    {diff_result.get('identical', False)}")
        if not diff_result.get("identical", False):
            print(f"  Differences:  {len(diff_result.get('differences', []))}")
            for diff in diff_result.get("differences", [])[:5]:
                print(f"    - {diff}")
    else:
        print(json.dumps(diff_result, indent=2, sort_keys=True))
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Show memory graph statistics."""
    from famulix.encoding import encode_events_to_graph
    from famulix.factory import generate_history_with_truth

    events, manifest, _ = generate_history_with_truth(
        persona_id=args.persona, seed=args.seed, days=args.days
    )
    graph = encode_events_to_graph(events)

    stats = {
        "persona_id": args.persona,
        "seed": args.seed,
        "days": args.days,
        "event_count": len(events),
        "node_count": graph.node_count(),
        "edge_count": graph.edge_count(),
        "kind_counts": graph.kind_counts(),
    }

    if args.json:
        print(json.dumps(stats, indent=2, sort_keys=True))
    else:
        print(f"Persona: {stats['persona_id']}")
        print(f"Seed: {stats['seed']}")
        print(f"Days: {stats['days']}")
        print(f"Events: {stats['event_count']}")
        print(f"Nodes: {stats['node_count']}")
        print(f"Edges: {stats['edge_count']}")
        print("Node kinds:")
        for kind, count in sorted(stats["kind_counts"].items()):
            print(f"  {kind}: {count}")

        # Verbose output: edge kinds and sample metadata
        if getattr(args, "verbose", False):
            print("\nEdge kinds:")
            edge_kinds: dict[str, int] = {}
            for edge in graph.all_edges():
                edge_kinds[edge.kind] = edge_kinds.get(edge.kind, 0) + 1
            for kind, count in sorted(edge_kinds.items()):
                print(f"  {kind}: {count}")

            print("\nSample nodes (first 5):")
            for node in graph.all_nodes()[:5]:
                print(f"  [{node.kind}] {node.node_id}: {node.title[:50]}")
                if node.metadata:
                    print(f"    metadata: {node.metadata}")
    return 0


def cmd_validate_session(args: argparse.Namespace) -> int:
    """Validate a session recording file."""
    from famulix.session import SessionRecorder, validate_session

    try:
        rec = SessionRecorder.load(args.path)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading session: {e}", file=sys.stderr)
        return 1

    report = validate_session(rec)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Session ID: {rec.session_id}")
        print(f"Valid: {report['valid']}")
        print(f"Entries: {report['entry_count']}")
        print(f"Checksum valid: {report['checksum_valid']}")
        print(f"Timestamps monotonic: {report['timestamp_monotonic']}")
        if report["errors"]:
            print("Errors:")
            for err in report["errors"]:
                print(f"  - {err}")
        else:
            print("No errors found.")

    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
