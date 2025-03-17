"""End-to-end contract for the runnable synthetic persona-day example."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def test_persona_day_writes_cited_briefing_and_scorecard(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "examples" / "04_persona_day.py"
    spec = importlib.util.spec_from_file_location("persona_day_example", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    html_path, score_path = module.run(tmp_path)
    html = html_path.read_text(encoding="utf-8")
    score = json.loads(score_path.read_text(encoding="utf-8"))
    assert html.startswith("<!DOCTYPE html>")
    assert "limitations" in html
    assert score["persona_id"] == "alex"
    assert score["seed"] == 23
    assert score["replay_deterministic"] is True
    assert score["budget_adherence"] is True
