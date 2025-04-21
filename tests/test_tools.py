"""Tests for tool specs, validation, and registry."""

from __future__ import annotations

from famulix.tools import ToolRegistry, ToolSpec, build_default_registry


def test_default_registry_has_echo_and_add() -> None:
    reg = build_default_registry()
    assert reg.has_tool("echo")
    assert reg.has_tool("add")
    specs = reg.list_specs()
    assert len(specs) == 2


def test_get_spec() -> None:
    reg = build_default_registry()
    spec = reg.get_spec("echo")
    assert spec is not None
    assert spec.name == "echo"
    assert spec.side_effect_class == "none"


def test_get_spec_missing() -> None:
    reg = build_default_registry()
    assert reg.get_spec("nonexistent") is None


def test_execute_echo() -> None:
    reg = build_default_registry()
    result = reg.execute("echo", {"text": "hello"})
    assert result.success
    assert result.output == "hello"
    assert result.tool_name == "echo"


def test_execute_add() -> None:
    reg = build_default_registry()
    result = reg.execute("add", {"a": 2.5, "b": 3.5})
    assert result.success
    assert result.output == 6.0


def test_execute_missing_tool() -> None:
    reg = build_default_registry()
    result = reg.execute("missing", {})
    assert not result.success
    assert "not found" in (result.error or "")


def test_validate_missing_required() -> None:
    reg = build_default_registry()
    result = reg.execute("echo", {})
    assert not result.success
    assert "missing required" in (result.error or "")


def test_validate_wrong_type() -> None:
    reg = build_default_registry()
    result = reg.execute("add", {"a": "not_a_number", "b": 2})
    assert not result.success
    assert "expected number" in (result.error or "")


def test_validate_unknown_field() -> None:
    reg = build_default_registry()
    result = reg.execute("echo", {"text": "hi", "extra": "field"})
    assert not result.success
    assert "unknown field" in (result.error or "")


def test_tool_validate_returns_errors() -> None:
    spec = ToolSpec(
        name="test",
        description="test",
        parameters={
            "type": "object",
            "properties": {
                "color": {"type": "string", "enum": ["red", "blue"]},
            },
            "required": ["color"],
        },
    )
    # Valid
    assert spec.validate_arguments({"color": "red"}) == []
    # Invalid enum value
    errors = spec.validate_arguments({"color": "green"})
    assert len(errors) == 1
    assert "enum" in errors[0]


def test_tool_result_has_receipt() -> None:
    reg = build_default_registry()
    result = reg.execute("echo", {"text": "hi"})
    assert result.receipt_id != ""
    assert "echo" in result.receipt_id


def test_idempotent_receipt_same_for_same_args() -> None:
    reg = build_default_registry()
    r1 = reg.execute("echo", {"text": "same"})
    r2 = reg.execute("echo", {"text": "same"})
    assert r1.receipt_id == r2.receipt_id


def test_different_args_different_receipt() -> None:
    reg = build_default_registry()
    r1 = reg.execute("echo", {"text": "a"})
    r2 = reg.execute("echo", {"text": "b"})
    assert r1.receipt_id != r2.receipt_id


def test_register_custom_tool() -> None:
    reg = ToolRegistry()

    def greet(name: str) -> str:
        return f"hello, {name}!"

    spec = ToolSpec(
        name="greet",
        description="Greet someone.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    )
    reg.register(spec, greet)
    result = reg.execute("greet", {"name": "world"})
    assert result.success
    assert result.output == "hello, world!"


def test_tool_receipt_is_stable_across_processes() -> None:
    import os
    import subprocess
    import sys

    code = (
        "from famulix.tools import build_default_registry; "
        "print(build_default_registry().execute("
        "'echo', {'text': 'same'}, idempotency_key='step').receipt_id)"
    )
    outputs = []
    for seed in ("17", "901"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": "src"}
        outputs.append(
            subprocess.check_output([sys.executable, "-c", code], env=env, text=True).strip()
        )
    assert outputs[0] == outputs[1]


def test_tool_argument_validation_enforces_types_and_declared_bounds() -> None:
    from famulix.tools import ToolSpec

    spec = ToolSpec(
        name="bounded",
        description="bounded values",
        parameters={
            "type": "object",
            "properties": {
                "count": {"type": "integer", "minimum": 1, "maximum": 4},
                "label": {"type": "string", "minLength": 2, "maxLength": 5},
                "ratio": {"type": "number"},
            },
            "required": ["count", "label", "ratio"],
        },
    )
    assert spec.validate_arguments({"count": 2, "label": "ok", "ratio": 0.5}) == []
    errors = spec.validate_arguments({"count": True, "label": "x", "ratio": float("inf")})
    assert any("expected integer" in error for error in errors)
    assert any("minLength" in error for error in errors)
    assert any("finite number" in error for error in errors)
    assert any(
        "minimum" in error
        for error in spec.validate_arguments({"count": 0, "label": "valid", "ratio": 1})
    )


def test_tool_spec_rejects_unsafe_retry_and_invalid_timeouts() -> None:
    import pytest

    from famulix.tools import ToolSpec

    with pytest.raises(ValueError, match="idempotent=True"):
        ToolSpec(
            name="write",
            description="write",
            parameters={},
            side_effect_class="write",
            max_retries=1,
        )
    with pytest.raises(ValueError, match="timeout"):
        ToolSpec(name="slow", description="slow", parameters={}, timeout_seconds=0)
    with pytest.raises(ValueError, match="max_retries"):
        ToolSpec(name="retry", description="retry", parameters={}, max_retries=-1)


def test_side_effect_tool_replays_receipt_without_repeating_handler() -> None:
    from famulix.tools import ToolRegistry, ToolSpec

    calls: list[str] = []
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="write",
            description="write",
            side_effect_class="write",
            idempotent=True,
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        ),
        lambda value: calls.append(value) or len(calls),
    )
    first = registry.execute("write", {"value": "one"}, idempotency_key="request-1")
    replay = registry.execute("write", {"value": "one"}, idempotency_key="request-1")
    collision = registry.execute("write", {"value": "two"}, idempotency_key="request-1")
    missing = registry.execute("write", {"value": "three"})
    assert first.output == replay.output == 1
    assert first.receipt_id == replay.receipt_id
    assert collision.success is False and "different arguments" in (collision.error or "")
    assert missing.success is False and "requires an idempotency key" in (missing.error or "")
    assert calls == ["one"]


def test_tool_result_receipt_roundtrip_and_schema_rejection() -> None:
    import pytest

    from famulix.tools import ToolResult

    original = ToolResult(
        tool_name="echo",
        success=True,
        output={"answer": 3},
        duration_s=0.125,
        retries=0,
        receipt_id="echo_abc",
    )
    payload = original.to_dict()
    assert ToolResult.from_dict(payload).to_dict() == payload
    with pytest.raises(ValueError, match="schema"):
        ToolResult.from_dict({**payload, "schema_version": 2})
    with pytest.raises(ValueError, match="fields"):
        ToolResult.from_dict({**payload, "success": 1})


def test_tool_registry_requires_declared_capability_grants() -> None:
    from famulix.tools import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="read_mail",
            description="read mail",
            parameters={"type": "object"},
            capability_tags=frozenset({"mail.read", "personal.data"}),
        ),
        lambda: "message",
    )
    denied = registry.execute("read_mail", {})
    allowed = registry.execute(
        "read_mail", {}, granted_capabilities={"mail.read", "personal.data", "extra"}
    )
    partial = registry.execute("read_mail", {}, granted_capabilities={"mail.read"})
    assert denied.success is False and "personal.data" in (denied.error or "")
    assert allowed.success is True and allowed.output == "message"
    assert partial.success is False


def test_tool_registry_lists_specs_in_name_order() -> None:
    from famulix.tools import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    for name in ("zeta", "alpha", "mu"):
        registry.register(
            ToolSpec(name=name, description=name, parameters={"type": "object"}),
            lambda: None,
        )
    assert [spec.name for spec in registry.list_specs()] == ["alpha", "mu", "zeta"]


def test_registry_rejects_duplicate_tool_names() -> None:
    import pytest

    from famulix.tools import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    registry.register(
        ToolSpec(name="same", description="first", parameters={"type": "object"}), lambda: "first"
    )
    with pytest.raises(ValueError, match="already registered"):
        registry.register(
            ToolSpec(name="same", description="second", parameters={"type": "object"}),
            lambda: "second",
        )
    assert registry.execute("same", {}).output == "first"


def test_tool_spec_rejects_malformed_schemas() -> None:
    import pytest

    from famulix.tools import ToolSpec

    with pytest.raises(ValueError, match="object schema"):
        ToolSpec(name="bad", description="bad", parameters={"type": "string"})
    with pytest.raises(ValueError, match="required fields"):
        ToolSpec(
            name="bad",
            description="bad",
            parameters={"type": "object", "properties": {}, "required": ["x"]},
        )
    with pytest.raises(ValueError, match="unsupported type"):
        ToolSpec(
            name="bad",
            description="bad",
            parameters={"type": "object", "properties": {"x": {"type": "record"}}},
        )
