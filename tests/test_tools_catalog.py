"""Test tool catalog generation."""

from famulix.tools import ToolRegistry, ToolSpec


def test_tool_catalog_empty():
    """Verify catalog generation for empty registry."""
    registry = ToolRegistry()
    catalog = registry.generate_catalog()

    assert "# Tool Catalog" in catalog
    assert "Total tools: 0" in catalog


def test_tool_catalog_with_tools():
    """Verify catalog includes tool details and parameters."""
    registry = ToolRegistry()

    spec = ToolSpec(
        name="example_tool",
        description="An example tool for testing",
        parameters={
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Input text"},
                "count": {"type": "integer"},
            },
            "required": ["input"],
        },
        side_effect_class="read",
        capability_tags=frozenset({"text"}),
        timeout_seconds=10.0,
    )

    registry.register(spec, lambda **kwargs: "result")

    catalog = registry.generate_catalog()

    assert "## example_tool" in catalog
    assert "An example tool for testing" in catalog
    assert "**Side effects**: read" in catalog
    assert "**Timeout**: 10.0s" in catalog
    assert "**Capabilities**: text" in catalog
    assert "`input`: string (required)" in catalog
    assert "`count`: integer" in catalog


def test_tool_catalog_with_enum():
    """Verify catalog includes enum values."""
    registry = ToolRegistry()

    spec = ToolSpec(
        name="enum_tool",
        description="Tool with enum parameter",
        parameters={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["fast", "slow", "balanced"],
                    "description": "Execution mode",
                }
            },
            "required": ["mode"],
        },
    )

    registry.register(spec, lambda **kwargs: "result")

    catalog = registry.generate_catalog()

    assert "Allowed values: fast, slow, balanced" in catalog
