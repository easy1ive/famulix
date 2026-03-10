"""Test approval info."""

from famulix.approval import approval_info


def test_approval_info():
    """Should return module info."""
    result = approval_info()
    assert result["module"] == "approval"
    assert result["version"] == "0.1.2"
