"""Test connectors info."""

from famulix.connectors import connectors_info


def test_connectors_info():
    """Should return module info."""
    result = connectors_info()
    assert result["module"] == "connectors"
    assert result["version"] == "0.1.2"
