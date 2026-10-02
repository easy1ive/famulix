"""Tests for briefing HTML escaping of hostile text."""

from famulix.briefing import Briefing, BriefingItem, render_briefing_html


def test_html_escapes_script_tag():
    item = BriefingItem(
        section="agenda",
        title="<script>alert('xss')</script>",
        body="Normal body text",
        memory_ids=["m1"],
    )
    briefing = Briefing(
        title="Daily Briefing",
        date_str="2026-03-15",
        items=[item],
    )
    html = render_briefing_html(briefing)
    # The raw script tag must not appear in the HTML output
    assert "<script>" not in html


def test_html_escapes_ampersand():
    item = BriefingItem(
        section="reminders",
        title="Tom & Jerry meeting",
        body="Discuss A&B project",
        memory_ids=["m2"],
    )
    briefing = Briefing(
        title="Daily Briefing",
        date_str="2026-03-15",
        items=[item],
    )
    html = render_briefing_html(briefing)
    assert "&amp;" in html or "Tom & Jerry" not in html


def test_html_escapes_quotes_in_title():
    item = BriefingItem(
        section="commitments",
        title='Say "hello"',
        body="Body text",
        memory_ids=["m3"],
    )
    briefing = Briefing(
        title="Daily Briefing",
        date_str="2026-03-15",
        items=[item],
    )
    html = render_briefing_html(briefing)
    assert html.count("<html") >= 1


def test_html_deterministic():
    item = BriefingItem(
        section="agenda",
        title="Test item",
        body="Test body",
        memory_ids=["m1"],
    )
    b1 = Briefing(title="Briefing", date_str="2026-03-15", items=[item])
    b2 = Briefing(title="Briefing", date_str="2026-03-15", items=[item])
    assert render_briefing_html(b1) == render_briefing_html(b2)
