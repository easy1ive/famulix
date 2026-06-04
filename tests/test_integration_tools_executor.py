"""Integration test: tools registry and validation.

Verifies that tools are registered correctly and validation works.
"""

from famulix.tools import ToolRegistry, ToolSpec, build_default_registry


def test_tool_registration_and_lookup():
    """Verify tools can be registered and retrieved."""
    registry = ToolRegistry()

    tool = ToolSpec(
        name="test_tool",
        description="A test tool",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        capability_tags=frozenset({"read"}),
        side_effect_class="read",
    )

    def handler(args):
        return {"result": args.get("query")}

    registry.register(tool, handler)

    retrieved = registry.get_spec("test_tool")
    assert retrieved is not None
    assert retrieved.name == "test_tool"
    assert retrieved.description == "A test tool"


def test_default_registry_has_tools():
    """Verify default registry has built-in tools."""
    registry = build_default_registry()

    # Should have echo and add tools
    echo = registry.get_spec("echo")
    assert echo is not None
    assert echo.name == "echo"

    add = registry.get_spec("add")
    assert add is not None
    assert add.name == "add"


def test_tool_spec_fields():
    """Verify tool specs have expected fields."""
    tool = ToolSpec(
        name="test",
        description="Test tool",
        parameters={"type": "object", "properties": {}, "required": []},
        capability_tags=frozenset({"read"}),
        side_effect_class="read",
    )

    assert tool.name == "test"
    assert tool.description == "Test tool"
    assert "read" in tool.capability_tags
    assert tool.side_effect_class == "read"


def test_tool_registry_list_tools():
    """Verify registry can list all registered tools."""
    registry = build_default_registry()

    specs = registry.list_specs()
    assert len(specs) >= 2  # At least echo and add

    names = {s.name for s in specs}
    assert "echo" in names
    assert "add" in names
