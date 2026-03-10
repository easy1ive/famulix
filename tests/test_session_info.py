"""Test session info."""

from famulix.session import session_info


def test_session_info():
    """Should return module info."""
    result = session_info()
    assert result["module"] == "session"
    assert result["version"] == "0.1.2"
