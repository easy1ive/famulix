"""Tests for briefing citation coverage: every cited memory must exist."""

from famulix.briefing import Briefing, BriefingItem


def test_all_cited_memory_ids():
    item1 = BriefingItem(section="agenda", title="Meeting", body="At 3pm", memory_ids=["m1", "m2"])
    item2 = BriefingItem(section="reminders", title="Call", body="Call dentist", memory_ids=["m3"])
    briefing = Briefing(title="Test", date_str="2026-03-15", items=[item1, item2])
    ids = briefing.all_cited_memory_ids()
    assert ids == {"m1", "m2", "m3"}


def test_citation_count():
    item = BriefingItem(section="agenda", title="Test", body="Body", memory_ids=["m1", "m2"])
    briefing = Briefing(title="Test", date_str="2026-03-15", items=[item])
    assert briefing.citation_count == 2


def test_item_count():
    items = [
        BriefingItem(section="a", title="A", body="a", memory_ids=["m1"]),
        BriefingItem(section="b", title="B", body="b", memory_ids=["m2"]),
    ]
    briefing = Briefing(title="Test", date_str="2026-03-15", items=items)
    assert briefing.item_count == 2


def test_empty_briefing():
    briefing = Briefing(title="Empty", date_str="2026-03-15", items=[])
    assert briefing.item_count == 0
    assert briefing.citation_count == 0


def test_briefing_to_dict_deterministic():
    item = BriefingItem(section="agenda", title="Test", body="Body", memory_ids=["m1"])
    b1 = Briefing(title="Test", date_str="2026-03-15", items=[item])
    b2 = Briefing(title="Test", date_str="2026-03-15", items=[item])
    assert b1.to_dict() == b2.to_dict()
