"""Tests for personalization layer."""

from __future__ import annotations

from famulix.personalization import (
    BriefingStyle,
    apply_preferences,
    counterfactual_compare,
    order_items,
)
from famulix.preferences import PreferenceProfile


def test_cold_start_defaults() -> None:
    p = PreferenceProfile()
    style = apply_preferences(p, now_s=100)
    assert isinstance(style, BriefingStyle)
    assert style.tone == "neutral"
    assert style.format == "markdown"
    assert style.ordering == "priority"
    assert style.length == "medium"


def test_cold_start_explanations() -> None:
    p = PreferenceProfile()
    style = apply_preferences(p, now_s=100)
    explanations = style.explain()
    assert len(explanations) == 4
    assert all("cold-start" in e for e in explanations)


def test_learned_tone_applied() -> None:
    p = PreferenceProfile()
    p.add_feedback("tone", "concise", "up", 100, 0.9)
    p.add_feedback("tone", "concise", "up", 200, 0.8)
    style = apply_preferences(p, now_s=300)
    assert style.tone == "concise"
    # Should have explanation with positive confidence
    tone_applied = [a for a in style.applied if a.key == "tone"][0]
    assert tone_applied.confidence > 0.0
    assert "learned" in tone_applied.reason


def test_learned_format_applied() -> None:
    p = PreferenceProfile()
    p.add_feedback("format", "html", "up", 100, 0.9)
    style = apply_preferences(p, now_s=200)
    assert style.format == "html"


def test_counterfactual_compare_identical() -> None:
    p1 = PreferenceProfile()
    p2 = PreferenceProfile()
    diff = counterfactual_compare(p1, p2, now_s=100)
    assert not any(d["changed"] for d in diff.values())


def test_counterfactual_compare_different() -> None:
    p1 = PreferenceProfile()
    p2 = PreferenceProfile()
    p2.add_feedback("tone", "concise", "up", 100, 1.0)
    diff = counterfactual_compare(p1, p2, now_s=200)
    assert diff["tone"]["changed"] is True


def test_order_items_priority() -> None:
    items = [
        {"title": "low", "priority": 0.2},
        {"title": "high", "priority": 0.9},
        {"title": "mid", "priority": 0.5},
    ]
    ordered = order_items(items, "priority")
    assert ordered[0]["title"] == "high"
    assert ordered[-1]["title"] == "low"


def test_order_items_recency() -> None:
    items = [
        {"title": "old", "timestamp_s": 100},
        {"title": "new", "timestamp_s": 300},
        {"title": "mid", "timestamp_s": 200},
    ]
    ordered = order_items(items, "recency")
    assert ordered[0]["title"] == "new"
    assert ordered[-1]["title"] == "old"


def test_order_items_category() -> None:
    items = [
        {"title": "c", "category": "work"},
        {"title": "a", "category": "personal"},
        {"title": "b", "category": "work"},
    ]
    ordered = order_items(items, "category")
    assert ordered[0]["category"] == "personal"
    assert ordered[-1]["category"] == "work"


def test_order_items_alphabetical() -> None:
    items = [{"title": "charlie"}, {"title": "alice"}, {"title": "bob"}]
    ordered = order_items(items, "alphabetical")
    assert [i["title"] for i in ordered] == ["alice", "bob", "charlie"]


def test_order_items_unknown_ordering_returns_copy() -> None:
    items = [{"title": "b"}, {"title": "a"}]
    ordered = order_items(items, "unknown")
    assert ordered == items
    assert ordered is not items  # new list
