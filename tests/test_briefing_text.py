"""Test briefing text renderer."""

from famulix.briefing import Briefing, BriefingItem, render_briefing_text


def test_render_empty_briefing():
    """Empty briefing should render without errors."""
    briefing = Briefing(
        title="Test Briefing",
        date_str="2026-11-12",
        sections=["agenda"],
        items=[],
        limitations=[],
        metadata={"date": "2026-11-12"},
    )
    text = render_briefing_text(briefing)
    assert "Test Briefing" in text


def test_render_with_items():
    """Briefing with items should include them in output."""
    briefing = Briefing(
        title="Daily Briefing",
        date_str="2026-11-12",
        sections=["agenda", "reminders"],
        items=[
            BriefingItem(
                section="agenda",
                title="Meeting",
                body="Team standup at 10am",
                memory_ids=["mem1", "mem2"],
            ),
        ],
        limitations=["Coverage is synthetic"],
        metadata={"date": "2026-11-12"},
    )
    text = render_briefing_text(briefing)
    assert "Meeting" in text
    assert "Team standup at 10am" in text
    assert "mem1" in text
    assert "LIMITATIONS" in text
    assert "Coverage is synthetic" in text


def test_render_text_no_markdown():
    """Text renderer should not include markdown formatting."""
    briefing = Briefing(
        title="Test",
        date_str="2026-11-12",
        sections=["agenda"],
        items=[
            BriefingItem(
                section="agenda",
                title="Item",
                body="Body",
                memory_ids=["m1"],
            ),
        ],
        limitations=[],
        metadata={},
    )
    text = render_briefing_text(briefing)
    # Should not have markdown headers
    assert "#" not in text
    # Should not have markdown links
    assert "[" not in text or "[cited:" in text
