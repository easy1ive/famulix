"""Test triggers info."""

from famulix.triggers import triggers_info


def test_triggers_info():
    """Should return module info."""
    result = triggers_info()
    assert result["module"] == "triggers"
    assert result["version"] == "0.1.2"
