"""Golden tests for consolidation tie-breaking edge cases."""

from famulix.consolidation import resolve_tie_by_trust


def test_trust_high_beats_medium():
    a = {"id": "mem_a", "trust": "high"}
    b = {"id": "mem_b", "trust": "medium"}
    assert resolve_tie_by_trust(a, b) == "mem_a"


def test_trust_medium_beats_low():
    a = {"id": "mem_a", "trust": "medium"}
    b = {"id": "mem_b", "trust": "low"}
    assert resolve_tie_by_trust(a, b) == "mem_a"


def test_equal_trust_lower_id_wins():
    a = {"id": "mem_aaa", "trust": "medium"}
    b = {"id": "mem_zzz", "trust": "medium"}
    assert resolve_tie_by_trust(a, b) == "mem_aaa"


def test_equal_trust_equal_id_returns_same():
    a = {"id": "mem_same", "trust": "high"}
    b = {"id": "mem_same", "trust": "high"}
    assert resolve_tie_by_trust(a, b) == "mem_same"


def test_missing_trust_defaults_to_medium():
    a = {"id": "mem_a"}
    b = {"id": "mem_b", "trust": "low"}
    assert resolve_tie_by_trust(a, b) == "mem_a"


def test_golden_tiebreak_sequence():
    """Stable sequence of tie-breaking outcomes across a fixed set of pairs."""
    pairs = [
        ({"id": "mem_001", "trust": "high"}, {"id": "mem_002", "trust": "medium"}),
        ({"id": "mem_003", "trust": "low"}, {"id": "mem_004", "trust": "low"}),
        ({"id": "mem_005", "trust": "medium"}, {"id": "mem_006", "trust": "high"}),
    ]
    winners = [resolve_tie_by_trust(a, b) for a, b in pairs]
    assert winners == ["mem_001", "mem_003", "mem_006"]
