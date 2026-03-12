"""Test privacy info."""

from famulix.privacy import privacy_info


def test_privacy_info():
    """Should return module info."""
    result = privacy_info()
    assert result["module"] == "privacy"
    assert result["version"] == "0.1.2"
