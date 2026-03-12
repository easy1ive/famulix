"""Test personalization info."""

from famulix.personalization import personalization_info


def test_personalization_info():
    """Should return module info."""
    result = personalization_info()
    assert result["module"] == "personalization"
    assert result["version"] == "0.1.2"
