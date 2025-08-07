"""Deterministic report rendering: Markdown + self-contained HTML + SVG.

No heavy plotting dependencies — all visuals are hand-emitted SVG.
Text is properly escaped for both Markdown and HTML contexts.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field


def escape_md(text: str) -> str:
    """Lightweight Markdown escaping for user-supplied text."""
    return text.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_")


def escape_html(text: str) -> str:
    """HTML-escape text."""
    return html.escape(text)


@dataclass
class ReportSection:
    """A section in a report."""

    title: str
    items: list[tuple[str, str]] = field(default_factory=list)  # (label, value)


def render_markdown(
    title: str,
    sections: list[ReportSection],
    *,
    metadata: dict[str, str] | None = None,
) -> str:
    """Render a report as Markdown."""
    lines: list[str] = []
    lines.append(f"# {escape_md(title)}")
    lines.append("")
    if metadata:
        lines.append("## Metadata")
        lines.append("")
        for k, v in metadata.items():
            lines.append(f"- **{escape_md(k)}**: {escape_md(v)}")
        lines.append("")
    for section in sections:
        lines.append(f"## {escape_md(section.title)}")
        lines.append("")
        if not section.items:
            lines.append("_No items._")
            lines.append("")
            continue
        for label, value in section.items:
            lines.append(f"- **{escape_md(label)}**: {escape_md(value)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_html(
    title: str,
    sections: list[ReportSection],
    *,
    metadata: dict[str, str] | None = None,
    svg_charts: list[str] | None = None,
    extra_css: str = "",
) -> str:
    """Render a self-contained HTML report."""
    css = (
        """
body { font-family: system-ui, -apple-system, sans-serif; max-width: 800px;
       margin: 2em auto; padding: 0 1em; color: #222; line-height: 1.6; }
h1, h2 { border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
section { margin-bottom: 2em; }
.metadata { background: #f7f7f7; padding: 1em; border-radius: 6px; font-size: 0.9em; }
.metadata dt { font-weight: bold; float: left; clear: left; width: 120px; }
.metadata dd { margin-left: 130px; }
ul { padding-left: 1.2em; }
svg { max-width: 100%; height: auto; }
"""
        + extra_css
    )
    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="zh-CN">')
    parts.append("<head>")
    parts.append('<meta charset="UTF-8">')
    parts.append(f"<title>{escape_html(title)}</title>")
    parts.append(f"<style>{css}</style>")
    parts.append("</head><body>")
    parts.append(f"<h1>{escape_html(title)}</h1>")

    if metadata:
        parts.append('<dl class="metadata">')
        for k, v in metadata.items():
            parts.append(f"<dt>{escape_html(k)}</dt><dd>{escape_html(v)}</dd>")
        parts.append("</dl>")

    for section in sections:
        parts.append("<section>")
        parts.append(f"<h2>{escape_html(section.title)}</h2>")
        if not section.items:
            parts.append("<p><em>No items.</em></p>")
        else:
            parts.append("<ul>")
            for label, value in section.items:
                parts.append(
                    f"<li><strong>{escape_html(label)}</strong>: {escape_html(value)}</li>"
                )
            parts.append("</ul>")
        parts.append("</section>")

    if svg_charts:
        parts.append("<section>")
        parts.append("<h2>Charts</h2>")
        for svg in svg_charts:
            parts.append(svg)
        parts.append("</section>")

    parts.append("</body></html>")
    return "\n".join(parts)


def svg_day_ribbon(
    hours: list[float],
    *,
    width: int = 600,
    height: int = 80,
    color: str = "#4a90d9",
) -> str:
    """Render a simple SVG day ribbon chart (24-hour activity pattern).

    hours is a list of 24 values representing activity level per hour.
    """
    if len(hours) != 24:
        raise ValueError("hours must have exactly 24 values")
    max_val = max(max(hours), 1.0)
    bar_w = width / 24
    points: list[str] = []
    for i, v in enumerate(hours):
        bar_h = (v / max_val) * (height - 10)
        x = i * bar_w
        y = height - bar_h
        points.append(f"{x:.1f},{y:.1f}")
        points.append(f"{x + bar_w:.1f},{y:.1f}")
    polyline_points = " ".join(points)
    svg = f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="#fafafa"/>
  <polyline points="{polyline_points}" fill="none" stroke="{color}" stroke-width="2"/>
</svg>'''
    return svg


def svg_heatmap(
    data: list[list[float]],
    *,
    cell_size: int = 20,
    title: str = "",
) -> str:
    """Render an SVG heatmap from a 2D array.

    data[row][col] is the value; rows are rendered top to bottom.
    """
    if not data or not data[0]:
        return "<svg/>"
    rows = len(data)
    cols = len(data[0])
    if any(len(row) != cols for row in data):
        raise ValueError("heatmap rows must have equal lengths")
    if any(not __import__("math").isfinite(value) or value < 0 for row in data for value in row):
        raise ValueError("heatmap values must be finite and non-negative")
    if type(cell_size) is not int or cell_size <= 0:
        raise ValueError("cell_size must be a positive integer")
    max_val = max(max(row) for row in data) or 1.0
    w = cols * cell_size
    h = rows * cell_size
    cells: list[str] = []
    for r, row in enumerate(data):
        for c, val in enumerate(row):
            intensity = min(val / max_val, 1.0)
            blue = int(255 - intensity * 180)
            green = int(255 - intensity * 120)
            color = f"rgb({int(255 - intensity * 150)}, {green}, {blue})"
            cells.append(
                f'<rect x="{c * cell_size}" y="{r * cell_size}" '
                f'width="{cell_size}" height="{cell_size}" fill="{color}"/>'
            )
    title_el = (
        f"<text x='{w / 2}' y='-5' text-anchor='middle' font-size='12'>{escape_html(title)}</text>"
        if title
        else ""
    )
    svg = f"""<svg viewBox="-10 -20 {w + 20} {h + 30}" xmlns="http://www.w3.org/2000/svg">
  {title_el}
  {"".join(cells)}
</svg>"""
    return svg


def svg_bar_chart(
    items: list[tuple[str, float]],
    *,
    title: str = "",
    width: int = 480,
    height: int = 200,
    color: str = "#4a90d9",
) -> str:
    """Render a simple SVG bar chart with labels.

    items: list of (label, value) tuples. Values are normalized to the max.
    """
    if not items:
        return "<svg/>"
    max_val = max(v for _, v in items) or 1.0
    bar_h = 18
    gap = 6
    pad_left = 120
    pad_right = 40
    pad_top = 28 if title else 8
    plot_w = width - pad_left - pad_right
    n = len(items)
    total_h = pad_top + n * (bar_h + gap) + 8

    bars: list[str] = []
    labels: list[str] = []
    for i, (label, value) in enumerate(items):
        y = pad_top + i * (bar_h + gap)
        w = max((value / max_val) * plot_w, 2)
        bars.append(
            f'<rect x="{pad_left}" y="{y:.1f}" width="{w:.1f}" height="{bar_h}" '
            f'fill="{color}" rx="3"/>'
        )
        labels.append(
            f'<text x="{pad_left - 6}" y="{y + 13:.1f}" text-anchor="end" '
            f'font-size="11" fill="#333">{escape_html(label[:24])}</text>'
        )
        # value label
        bars.append(
            f'<text x="{pad_left + w + 4:.1f}" y="{y + 13:.1f}" '
            f'font-size="10" fill="#666">{value:.2f}</text>'
        )

    title_el = (
        f'<text x="{width / 2}" y="18" text-anchor="middle" font-size="14" '
        f'font-weight="bold" fill="#222">{escape_html(title)}</text>'
        if title
        else ""
    )

    svg = f"""<svg viewBox="0 0 {width} {total_h}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{total_h}" fill="#fafafa"/>
  {title_el}
  {"".join(bars)}
  {"".join(labels)}
</svg>"""
    return svg


def svg_commitment_timeline(
    items: list[tuple[str, float, float]],
    *,
    width: int = 600,
    height: int = 120,
) -> str:
    """Render an SVG commitment timeline.

    items is a list of (label, start_day, duration_days). Day 0 is leftmost.
    """
    if not items:
        return "<svg/>"
    max_day = max(start + dur for _, start, dur in items) or 1.0
    row_h = 22
    pad_left = 120
    pad_right = 20
    plot_w = width - pad_left - pad_right
    bars: list[str] = []
    labels: list[str] = []
    for i, (label, start, dur) in enumerate(items):
        y = i * row_h + 10
        x = pad_left + (start / max_day) * plot_w
        w = max((dur / max_day) * plot_w, 2)
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="14" fill="#4a90d9" rx="3"/>'
        )
        labels.append(
            f'<text x="{pad_left - 6}" y="{y + 11:.1f}" text-anchor="end" '
            f'font-size="11" fill="#333">{escape_html(label[:24])}</text>'
        )
    total_h = max(len(items) * row_h + 20, height)
    svg = f"""<svg viewBox="0 0 {width} {total_h}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{total_h}" fill="#fafafa"/>
  <line x1="{pad_left}" y1="5" x2="{pad_left}" y2="{total_h - 5}" stroke="#ddd"/>
  {"".join(bars)}
  {"".join(labels)}
</svg>"""
    return svg


def run_metadata(
    *,
    version: str,
    seed: int,
    config_hash: str,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a standard metadata dict for report headers."""
    meta = {
        "version": version,
        "seed": str(seed),
        "config_hash": config_hash,
    }
    if extra:
        meta.update(extra)
    return meta


def _as_timestamp(value: object) -> int:
    """Coerce a node-dict timestamp to an int, treating unusable values as 0.

    Node dicts arrive from serialised graphs and from hand-written fixtures, so
    the timestamp may be an int, a float, a numeric string, ``None`` or junk.
    The timeline must stay renderable and deterministic in every case instead
    of raising part-way through a report.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return 0
    return 0


def memory_timeline_markdown(
    nodes: list[dict[str, object]],
    *,
    title: str = "Memory Timeline",
) -> str:
    """Render a simple Markdown timeline from node dicts sorted by created_at."""
    sorted_nodes = sorted(nodes, key=lambda n: _as_timestamp(n.get("created_at_s", 0)))
    sections: list[ReportSection] = []
    items: list[tuple[str, str]] = []
    for n in sorted_nodes:
        label = str(n.get("title", "(untitled)"))
        ts = _as_timestamp(n.get("created_at_s", 0))
        kind = str(n.get("kind", "?"))
        value = f"[{kind}] t={ts} — {n.get('body', '')}"
        items.append((label, value))
    sections.append(ReportSection(title="timeline", items=items))
    return render_markdown(title, sections)


def json_escape(data: object) -> str:
    """Deterministic JSON serialization for embedded data."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False)
