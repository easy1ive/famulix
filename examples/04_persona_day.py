"""Run a seeded synthetic day through memory, briefing, and evaluation.

Run: python examples/04_persona_day.py [output-directory]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from famulix.briefing import build_briefing, render_briefing_html
from famulix.consolidation import consolidate_graph
from famulix.encoding import encode_events_to_graph
from famulix.evaluation import run_full_evaluation
from famulix.factory import generate_history_with_truth


def run(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    events, manifest, _truth = generate_history_with_truth(
        "alex", seed=23, days=14, start_date="2026-10-01"
    )
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)
    now_s = events[-1].timestamp_s + 3600
    briefing = build_briefing(
        graph,
        date_str=manifest.end_date,
        now_s=now_s,
        budget_tokens=350,
        seed=23,
        config_hash=manifest.checksum,
    )
    if not briefing.citations_resolve(graph):
        raise RuntimeError("briefing contains an unresolved memory citation")
    html_path = output_dir / "daily-briefing.html"
    html_path.write_text(render_briefing_html(briefing, graph=graph), encoding="utf-8")

    scorecard = run_full_evaluation("alex", seed=23, days=14, start_date="2026-10-01")
    score_path = output_dir / "scorecard.json"
    score_path.write_text(
        json.dumps(scorecard.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return html_path, score_path


def main() -> int:
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("artifacts/persona-day")
    html_path, score_path = run(destination)
    print(f"HTML briefing: {html_path}")
    print(f"Synthetic evaluation scorecard: {score_path}")
    print(
        "Results describe a seeded synthetic history; no external model or personal data is used."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
