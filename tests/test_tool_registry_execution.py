"""Tests for tool registry execution and built-in tool behavior."""

from famulix.tools import build_default_registry


def test_builtin_tools_registered():
    registry = build_default_registry()
    assert registry.has_tool("echo")
    assert registry.has_tool("add")


def test_echo_tool_returns_input():
    registry = build_default_registry()
    result = registry.execute("echo", {"text": "test message"})
    assert result.success
    assert result.output == "test message"


def test_add_tool_returns_sum():
    registry = build_default_registry()
    result = registry.execute("add", {"a": 3.0, "b": 4.0})
    assert result.success
    assert result.output == 7.0


def test_add_tool_deterministic():
    registry = build_default_registry()
    r1 = registry.execute("add", {"a": 1.5, "b": 2.5})
    r2 = registry.execute("add", {"a": 1.5, "b": 2.5})
    assert r1.output == r2.output


def test_unknown_tool_returns_error():
    registry = build_default_registry()
    result = registry.execute("nonexistent_tool", {"x": 1})
    assert not result.success


def test_tool_count():
    registry = build_default_registry()
    assert registry.tool_count() == 2


def test_list_specs_sorted():
    registry = build_default_registry()
    specs = registry.list_specs()
    assert len(specs) == 2
    names = [s.name for s in specs]
    assert names == sorted(names)
