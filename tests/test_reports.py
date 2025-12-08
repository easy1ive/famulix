"""Tests for report rendering."""

from __future__ import annotations

from famulix.reports import (
    ReportSection,
    escape_html,
    escape_md,
    json_escape,
    render_html,
    render_markdown,
    run_metadata,
    svg_day_ribbon,
    svg_heatmap,
)


def test_render_markdown_basic() -> None:
    sections = [ReportSection(title="Test", items=[("a", "1"), ("b", "2")])]
    md = render_markdown("My Report", sections)
    assert "# My Report" in md
    assert "## Test" in md
    assert "**a**: 1" in md
    assert "**b**: 2" in md


def test_render_markdown_with_metadata() -> None:
    meta = {"version": "0.1.0", "seed": "42"}
    md = render_markdown("R", [], metadata=meta)
    assert "## Metadata" in md
    assert "version" in md
    assert "0.1.0" in md


def test_render_html_basic() -> None:
    sections = [ReportSection(title="Intro", items=[("key", "val")])]
    html = render_html("Hello", sections)
    assert "<!DOCTYPE html>" in html
    assert "<h1>Hello</h1>" in html
    assert "<h2>Intro</h2>" in html
    assert "<strong>key</strong>" in html


def test_render_html_escapes_user_text() -> None:
    sections = [ReportSection(title="X", items=[("<script>", "</script>")])]
    html = render_html("Test", sections)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_escape_html() -> None:
    assert escape_html("<b>") == "&lt;b&gt;"


def test_escape_md() -> None:
    assert "*bold*" not in escape_md("*bold*")


def test_svg_day_ribbon_requires_24_hours() -> None:
    import pytest

    with pytest.raises(ValueError):
        svg_day_ribbon([1, 2, 3])


def test_svg_day_ribbon_renders_svg() -> None:
    hours = [float(i) for i in range(24)]
    svg = svg_day_ribbon(hours)
    assert "<svg" in svg
    assert "polyline" in svg
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg


def test_svg_day_ribbon_deterministic() -> None:
    hours = [float(i) for i in range(24)]
    assert svg_day_ribbon(hours) == svg_day_ribbon(hours)


def test_svg_heatmap_basic() -> None:
    data = [[1.0, 0.5], [0.3, 0.9]]
    svg = svg_heatmap(data, title="test")
    assert "<svg" in svg
    assert "<rect" in svg
    assert "test" in svg


def test_svg_heatmap_empty() -> None:
    assert svg_heatmap([]) == "<svg/>"


def test_run_metadata() -> None:
    meta = run_metadata(version="0.1.0", seed=42, config_hash="abc123")
    assert meta["version"] == "0.1.0"
    assert meta["seed"] == "42"
    assert meta["config_hash"] == "abc123"


def test_run_metadata_extra() -> None:
    meta = run_metadata(version="v", seed=0, config_hash="h", extra={"extra_key": "val"})
    assert meta["extra_key"] == "val"


def test_json_escape_sorted() -> None:
    assert json_escape({"b": 2, "a": 1}) == json_escape({"a": 1, "b": 2})


def test_render_markdown_empty_section() -> None:
    sections = [ReportSection(title="Empty")]
    md = render_markdown("R", sections)
    assert "No items" in md


def test_render_html_with_svg_charts() -> None:
    svg = "<svg>test</svg>"
    html = render_html("R", [], svg_charts=[svg])
    assert "Charts" in html
    assert "<svg>test</svg>" in html


def test_heatmap_rejects_ragged_or_invalid_data() -> None:
    import pytest

    with pytest.raises(ValueError, match="equal lengths"):
        svg_heatmap([[1.0, 2.0], [3.0]])
    with pytest.raises(ValueError, match="finite and non-negative"):
        svg_heatmap([[float("nan")]])
    with pytest.raises(ValueError, match="cell_size"):
        svg_heatmap([[1.0]], cell_size=0)


def test_svg_commitment_timeline_renders_bars_for_each_item() -> None:
    from famulix.reports import svg_commitment_timeline

    items = [("report", 3.0, 7.0), ("gym plan", 0.0, 30.0)]
    svg = svg_commitment_timeline(items)
    assert svg.count("<rect") == 2 + 1  # bars + background
    assert "report" in svg
    assert "gym plan" in svg


def test_svg_commitment_timeline_empty_returns_tiny_svg() -> None:
    from famulix.reports import svg_commitment_timeline

    assert svg_commitment_timeline([]) == "<svg/>"


def test_memory_timeline_sorts_by_created_at() -> None:
    from famulix.reports import memory_timeline_markdown

    nodes = [
        {"title": "later", "created_at_s": 200, "kind": "fact", "body": "b"},
        {"title": "earlier", "created_at_s": 100, "kind": "fact", "body": "a"},
    ]
    md = memory_timeline_markdown(nodes)
    assert md.index("earlier") < md.index("later")


def test_memory_timeline_escapes_md_special_chars() -> None:
    from famulix.reports import memory_timeline_markdown

    nodes = [{"title": "x*_test", "created_at_s": 1, "kind": "fact", "body": "a*b_c"}]
    md = memory_timeline_markdown(nodes)
    # escape_md backslash-escapes * and _
    assert "\\*" in md
    assert "\\_" in md


def test_svg_bar_chart_renders_svg() -> None:
    from famulix.reports import svg_bar_chart

    items = [("alpha", 3.0), ("beta", 5.0), ("gamma", 2.0)]
    svg = svg_bar_chart(items, title="Test Chart")
    assert "<svg" in svg
    assert "</svg>" in svg
    # Each label appears in the chart
    for label, _ in items:
        assert label in svg
    assert "Test Chart" in svg


def test_svg_bar_chart_empty_returns_empty_svg() -> None:
    from famulix.reports import svg_bar_chart

    assert svg_bar_chart([]) == "<svg/>"


def test_svg_bar_chart_escapes_labels() -> None:
    from famulix.reports import svg_bar_chart

    svg = svg_bar_chart([("<script>", 1.0)])
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


def test_as_timestamp_coerces_supported_shapes_and_rejects_junk() -> None:
    from famulix.reports import _as_timestamp

    assert _as_timestamp(1700000000) == 1700000000
    assert _as_timestamp(1700000000.9) == 1700000000
    assert _as_timestamp("  42 ") == 42
    assert _as_timestamp(-5) == -5
    assert _as_timestamp(0) == 0
    for junk in (None, "", "soon", True, [1], {"a": 1}):
        assert _as_timestamp(junk) == 0


def test_memory_timeline_renders_with_mixed_timestamp_types() -> None:
    from famulix.reports import memory_timeline_markdown

    nodes = [
        {"title": "later", "kind": "fact", "body": "b", "created_at_s": 300},
        {"title": "textual", "kind": "fact", "body": "b", "created_at_s": "200"},
        {"title": "missing", "kind": "fact", "body": "b"},
        {"title": "junk", "kind": "fact", "body": "b", "created_at_s": None},
    ]
    rendered = memory_timeline_markdown(nodes)
    positions = [rendered.index(name) for name in ("missing", "junk", "textual", "later")]
    assert positions == sorted(positions)
    assert "t=300" in rendered
    assert "t=200" in rendered


def test_config_hash_deterministic_for_same_input() -> None:
    from famulix.reports import config_hash

    config = {"key1": "value1", "key2": 42, "key3": True}
    hash1 = config_hash(config)
    hash2 = config_hash(config)
    assert hash1 == hash2
    assert len(hash1) == 16


def test_config_hash_differs_for_different_input() -> None:
    from famulix.reports import config_hash

    hash1 = config_hash({"a": 1})
    hash2 = config_hash({"a": 2})
    assert hash1 != hash2


def test_config_hash_order_independent() -> None:
    from famulix.reports import config_hash

    hash1 = config_hash({"a": 1, "b": 2})
    hash2 = config_hash({"b": 2, "a": 1})
    assert hash1 == hash2


def test_render_limitations_formats_issues() -> None:
    from famulix.reports import render_limitations

    issues = ["No real LLM evaluation", "Synthetic data only"]
    result = render_limitations(issues)
    assert "## Limitations" in result
    assert "No real LLM evaluation" in result
    assert "Synthetic data only" in result


def test_render_limitations_empty_returns_empty() -> None:
    from famulix.reports import render_limitations

    assert render_limitations([]) == ""


def test_validate_report_sections_valid() -> None:
    from famulix.reports import ReportSection, validate_report_sections

    sections = [
        ReportSection(title="Section A", items=[("label1", "value1")]),
        ReportSection(title="Section B", items=[("label2", "value2")]),
    ]
    problems = validate_report_sections(sections)
    assert problems == []


def test_validate_report_sections_empty() -> None:
    from famulix.reports import validate_report_sections

    problems = validate_report_sections([])
    assert problems == []


def test_validate_report_sections_detects_problems() -> None:
    from famulix.reports import ReportSection, validate_report_sections

    sections = [
        ReportSection(title="", items=[("label", "value")]),
        ReportSection(title="Duplicate", items=[("", "value")]),
        ReportSection(title="Duplicate", items=[("label", "value")]),
    ]
    problems = validate_report_sections(sections)
    assert len(problems) >= 3
    assert any("empty title" in p for p in problems)
    assert any("duplicate" in p for p in problems)
    assert any("empty label" in p for p in problems)


def test_generate_comprehensive_report_empty() -> None:
    from famulix.reports import generate_comprehensive_report

    report = generate_comprehensive_report(title="Empty Report")
    assert "# Empty Report" in report


def test_generate_comprehensive_report_with_data() -> None:
    from famulix.reports import generate_comprehensive_report

    report = generate_comprehensive_report(
        title="Test Report",
        metadata={"version": "1.0", "date": "2026-01-01"},
        memory_stats={"total": 100, "active": 80},
        retrieval_stats={"recall": 0.95, "precision": 0.88},
        consolidation_stats={"merged": 5, "superseded": 2},
        limitations=["Synthetic data only"],
    )
    assert "# Test Report" in report
    assert "## Metadata" in report
    assert "## Memory Statistics" in report
    assert "## Retrieval Performance" in report
    assert "## Consolidation Summary" in report
    assert "## Known Limitations" in report
