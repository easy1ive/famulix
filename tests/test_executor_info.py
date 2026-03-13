"""Test executor info."""

from famulix.executor import executor_info


def test_executor_info():
    """Should return module info."""
    result = executor_info()
    assert result["module"] == "executor"
    assert result["version"] == "0.1.2"
