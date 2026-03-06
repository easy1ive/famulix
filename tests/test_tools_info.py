"""Test tools info."""

from famulix.tools import tools_info


def test_tools_info():
    """Should return module info."""
    result = tools_info()
    assert result["module"] == "tools"
    assert result["version"] == "0.1.2"
