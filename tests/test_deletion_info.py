"""Test deletion info."""

from famulix.deletion import deletion_info


def test_deletion_info():
    """Should return module info."""
    result = deletion_info()
    assert result["module"] == "deletion"
    assert result["version"] == "0.1.2"
