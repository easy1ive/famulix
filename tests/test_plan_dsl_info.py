"""Test plan_dsl info."""

from famulix.plan_dsl import plan_dsl_info


def test_plan_dsl_info():
    """Should return module info."""
    result = plan_dsl_info()
    assert result["module"] == "plan_dsl"
    assert result["version"] == "0.1.2"
