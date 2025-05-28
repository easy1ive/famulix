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
