"""Test fact key extraction for contradiction detection."""

from famulix.consolidation import extract_fact_key


def test_fact_key_captures_core_meaning():
    k1 = extract_fact_key("My address is 123 Main St")
    k2 = extract_fact_key("I live at 123 Main St")
    assert k1 == k2 or set(k1.split()) & set(k2.split())


def test_fact_key_different_facts_differ():
    k1 = extract_fact_key("My phone is 555-1234")
    k2 = extract_fact_key("My email is test@example.com")
    assert k1 != k2


def test_fact_key_handles_empty():
    k = extract_fact_key("")
    assert isinstance(k, str)
