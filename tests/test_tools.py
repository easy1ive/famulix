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


def test_preflight_validates_without_calling_handler() -> None:
    from famulix.tools import ToolRegistry, ToolSpec

    calls: list[str] = []
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="private",
            description="private",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            capability_tags=frozenset({"private.read"}),
        ),
        lambda text: calls.append(text),
    )
    errors = registry.preflight("private", {})
    assert any("missing required field" in error for error in errors)
    assert any("missing capabilities" in error for error in errors)
    assert calls == []
    assert registry.preflight("unknown", {}) == ["tool not found: unknown"]


def test_tool_count_matches_registered() -> None:
    from famulix.tools import build_default_registry

    registry = build_default_registry()
    assert registry.tool_count() == len(registry.list_specs())


def test_tools_by_capability_filters_correctly() -> None:
    from famulix.tools import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="read_notes",
            description="read notes",
            parameters={"type": "object", "properties": {}, "required": []},
            capability_tags=frozenset({"notes.read", "memory"}),
        ),
        lambda: "notes",
    )
    registry.register(
        ToolSpec(
            name="read_calendar",
            description="read calendar",
            parameters={"type": "object", "properties": {}, "required": []},
            capability_tags=frozenset({"calendar.read", "memory"}),
        ),
        lambda: "calendar",
    )
    registry.register(
        ToolSpec(
            name="send_email",
            description="send email",
            parameters={"type": "object", "properties": {}, "required": []},
            side_effect_class="write",
            idempotent=True,
            capability_tags=frozenset({"email.write"}),
        ),
        lambda: "sent",
    )
    memory_tools = registry.tools_by_capability("memory")
    assert len(memory_tools) == 2
    assert {t.name for t in memory_tools} == {"read_notes", "read_calendar"}
    email_tools = registry.tools_by_capability("email.write")
    assert len(email_tools) == 1
    assert email_tools[0].name == "send_email"


def test_side_effect_summary_counts_by_class() -> None:
    from famulix.tools import build_default_registry

    registry = build_default_registry()
    summary = registry.side_effect_summary()
    assert sum(summary.values()) == registry.tool_count()
    # default registry has tools with side_effect_class "none"
    assert "none" in summary


def _receipt_payload() -> dict[str, object]:
    from famulix.tools import ToolResult

    result = ToolResult(
        tool_name="echo",
        success=True,
        output="hi",
        error=None,
        duration_s=0.5,
        retries=0,
        receipt_id="echo_abc",
    )
    return result.to_dict()


def test_receipt_from_dict_rejects_non_numeric_durations() -> None:
    import pytest

    from famulix.tools import ToolResult

    for bad in ("fast", None, True, [0.5], {"s": 1}):
        payload = dict(_receipt_payload())
        payload["duration_s"] = bad
        with pytest.raises(ValueError, match="real number"):
            ToolResult.from_dict(payload)


def test_receipt_from_dict_rejects_infinite_durations() -> None:
    import math

    import pytest

    from famulix.tools import ToolResult

    for infinite in (math.inf, -math.inf, math.nan):
        payload = dict(_receipt_payload())
        payload["duration_s"] = infinite
        with pytest.raises(ValueError, match="finite"):
            ToolResult.from_dict(payload)


def test_receipt_from_dict_accepts_int_and_float_durations() -> None:
    from famulix.tools import ToolResult

    for duration in (0, 2, 1.25):
        payload = dict(_receipt_payload())
        payload["duration_s"] = duration
        assert ToolResult.from_dict(payload).duration_s == float(duration)


def test_tool_registry_idempotency_key_tracking() -> None:
    from famulix.tools import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    spec = ToolSpec(
        name="write_tool",
        description="A write tool",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        side_effect_class="write",
        idempotent=True,
    )
    registry.register(spec, lambda value: {"result": value})
    assert registry.idempotency_key_count() == 0
    registry.execute("write_tool", {"value": "test"}, idempotency_key="key1")
    assert registry.idempotency_key_count() == 1
    assert registry.has_idempotency_key("write_tool", "key1")
    assert not registry.has_idempotency_key("write_tool", "key2")


def test_tool_registry_idempotency_replay_returns_same_result() -> None:
    from famulix.tools import ToolRegistry, ToolSpec

    call_count = 0

    def handler(value: str) -> dict[str, str]:
        nonlocal call_count
        call_count += 1
        return {"result": value, "call": str(call_count)}

    registry = ToolRegistry()
    spec = ToolSpec(
        name="write_tool",
        description="A write tool",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        side_effect_class="write",
        idempotent=True,
    )
    registry.register(spec, handler)
    result1 = registry.execute("write_tool", {"value": "test"}, idempotency_key="key1")
    result2 = registry.execute("write_tool", {"value": "test"}, idempotency_key="key1")
    assert call_count == 1
    assert result1.output == result2.output
    assert result1.success and result2.success


def test_tool_registry_clear_idempotency_cache() -> None:
    from famulix.tools import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    spec = ToolSpec(
        name="write_tool",
        description="A write tool",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        side_effect_class="write",
        idempotent=True,
    )
    registry.register(spec, lambda value: {"result": value})
    registry.execute("write_tool", {"value": "test1"}, idempotency_key="key1")
    registry.execute("write_tool", {"value": "test2"}, idempotency_key="key2")
    assert registry.idempotency_key_count() == 2
    cleared = registry.clear_idempotency_cache()
    assert cleared == 2
    assert registry.idempotency_key_count() == 0
