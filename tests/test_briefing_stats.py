"""Test briefing statistics."""

from famulix.briefing import Briefing, BriefingItem, briefing_stats


def test_briefing_stats():
    """Should extract briefing fields."""
    briefing = Briefing(
        title="Test",
        date_str="2026-11-12",
        sections=["agenda", "reminders"],
        items=[
            BriefingItem(
                section="agenda",
                title="Meeting",
                body="Body",
                memory_ids=["m1", "m2"],
            ),
        ],
        limitations=["Synthetic coverage"],
        metadata={},
    )
    stats = briefing_stats(briefing)
    assert stats["item_count"] == 1
    assert stats["citation_count"] == 2
    assert stats["section_count"] == 2
    assert stats["limitation_count"] == 1
