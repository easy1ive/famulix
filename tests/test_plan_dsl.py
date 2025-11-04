"""Tests for plan DSL: validation, topological order, diff."""

from __future__ import annotations

from famulix.plan_dsl import (
    Plan,
    PlanStep,
    plan_diff,
    topological_order,
    validate_plan,
)


def test_empty_plan_valid() -> None:
    plan = Plan(plan_id="p1")
    result = validate_plan(plan)
    assert result.valid


def test_single_step_valid() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[PlanStep(id="s1", tool="echo", inputs={"text": "hi"})],
    )
    result = validate_plan(plan)
    assert result.valid
    assert result.errors == []


def test_dangling_dependency_invalid() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "a"}, depends_on=["s99"]),
        ],
    )
    result = validate_plan(plan)
    assert not result.valid
    assert any("dangling" in e for e in result.errors)


def test_cycle_detected() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "a"}, depends_on=["s2"]),
            PlanStep(id="s2", tool="echo", inputs={"text": "b"}, depends_on=["s1"]),
        ],
    )
    result = validate_plan(plan)
    assert not result.valid
    assert any("cycle" in e for e in result.errors)


def test_linear_chain_valid() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "a"}),
            PlanStep(id="s2", tool="echo", inputs={"text": "b"}, depends_on=["s1"]),
            PlanStep(id="s3", tool="echo", inputs={"text": "c"}, depends_on=["s2"]),
        ],
    )
    result = validate_plan(plan)
    assert result.valid


def test_topological_order_linear() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s3", tool="echo", inputs={}, depends_on=["s2"]),
            PlanStep(id="s1", tool="echo", inputs={}),
            PlanStep(id="s2", tool="echo", inputs={}, depends_on=["s1"]),
        ],
    )
    order = topological_order(plan)
    assert order.index("s1") < order.index("s2") < order.index("s3")


def test_topological_order_deterministic() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="z", tool="echo", inputs={}),
            PlanStep(id="a", tool="echo", inputs={}),
            PlanStep(id="m", tool="echo", inputs={}),
        ],
    )
    order1 = topological_order(plan)
    order2 = topological_order(plan)
    assert order1 == order2
    # Entry points sorted alphabetically
    assert order1 == ["a", "m", "z"]


def test_topological_order_with_cycle_partial() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={}, depends_on=["s2"]),
            PlanStep(id="s2", tool="echo", inputs={}, depends_on=["s1"]),
            PlanStep(id="s3", tool="echo", inputs={}),
        ],
    )
    order = topological_order(plan)
    # s3 has no deps and should be in the order
    assert "s3" in order


def test_duplicate_step_ids_invalid() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "a"}),
            PlanStep(id="s1", tool="echo", inputs={"text": "b"}),
        ],
    )
    result = validate_plan(plan)
    assert not result.valid
    assert any("duplicate" in e for e in result.errors)


def test_plan_diff_added_removed_modified() -> None:
    a = Plan(
        plan_id="p",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "a"}),
            PlanStep(id="s2", tool="echo", inputs={"text": "b"}),
        ],
    )
    b = Plan(
        plan_id="p",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "a-modified"}),
            PlanStep(id="s3", tool="echo", inputs={"text": "c"}),
        ],
    )
    diff = plan_diff(a, b)
    assert "s3" in diff["added"]
    assert "s2" in diff["removed"]
    assert "s1" in diff["modified"]


def test_plan_diff_identical() -> None:
    a = Plan(
        plan_id="p",
        steps=[PlanStep(id="s1", tool="echo", inputs={"x": 1})],
    )
    b = Plan(
        plan_id="p",
        steps=[PlanStep(id="s1", tool="echo", inputs={"x": 1})],
    )
    diff = plan_diff(a, b)
    assert diff["added"] == []
    assert diff["removed"] == []
    assert diff["modified"] == []


def test_plan_to_dict() -> None:
    plan = Plan(plan_id="test", steps=[PlanStep(id="s1", tool="echo", inputs={"t": "x"})])
    d = plan.to_dict()
    assert d["plan_id"] == "test"
    assert len(d["steps"]) == 1
    assert d["steps"][0]["id"] == "s1"


def test_plan_get_step() -> None:
    plan = Plan(
        plan_id="p",
        steps=[PlanStep(id="s1", tool="echo"), PlanStep(id="s2", tool="add")],
    )
    assert plan.get_step("s1").tool == "echo"
    assert plan.get_step("missing") is None


def test_plan_json_roundtrip_has_versioned_golden_shape() -> None:
    plan = Plan(plan_id="daily", steps=[PlanStep(id="read", tool="echo", inputs={"text": "hi"})])
    payload = plan.to_json()
    expected = (
        '{"max_budget":0.0,"metadata":{},"plan_id":"daily","schema_version":1,'
        '"steps":[{"budget":0.0,"depends_on":[],"effects":[],"id":"read",'
        '"input_types":{},"inputs":{"text":"hi"},"output_types":{},"preconditions":[],'
        '"timeout_s":5.0,"tool":"echo"}],"version":1}'
    )
    assert payload == expected
    assert Plan.from_json(payload).to_json() == payload


def test_plan_decoder_rejects_unsupported_and_malformed_payloads() -> None:
    import pytest

    plan = Plan(plan_id="p", steps=[PlanStep(id="s", tool="echo")])
    payload = plan.to_dict()
    with pytest.raises(ValueError, match="schema version"):
        Plan.from_dict({**payload, "schema_version": 2})
    with pytest.raises(ValueError, match="unknown or missing"):
        Plan.from_dict({**payload, "extra": True})
    bad = {**payload, "steps": [{"id": "s"}]}
    with pytest.raises(ValueError, match="unknown or missing"):
        Plan.from_dict(bad)


def test_plan_validation_rejects_invalid_identity_limits_and_duplicate_edges() -> None:
    plan = Plan(
        plan_id="", version=0, steps=[PlanStep(id="s", tool="", depends_on=["s", "s"], timeout_s=0)]
    )
    result = validate_plan(plan)
    assert not result.valid
    assert any("plan id" in error for error in result.errors)
    assert any("version" in error for error in result.errors)
    assert any("duplicate dependencies" in error for error in result.errors)
    assert any("timeout" in error for error in result.errors)


def test_plan_validation_rejects_non_finite_step_limits() -> None:
    plan = Plan(plan_id="finite", steps=[PlanStep(id="s", tool="echo", timeout_s=float("nan"))])
    result = validate_plan(plan)
    assert not result.valid
    assert any("timeout" in error for error in result.errors)


def test_plan_fingerprint_changes_with_content_and_survives_roundtrip() -> None:
    from famulix.plan_dsl import Plan, PlanStep

    first = Plan(plan_id="digest", steps=[PlanStep(id="s", tool="echo", inputs={"text": "a"})])
    changed = Plan(plan_id="digest", steps=[PlanStep(id="s", tool="echo", inputs={"text": "b"})])
    assert first.fingerprint() == Plan.from_json(first.to_json()).fingerprint()
    assert first.fingerprint() != changed.fingerprint()


def test_plan_json_rejects_non_object_payload() -> None:
    import pytest

    with pytest.raises(ValueError, match="object"):
        Plan.from_json("[]")


def test_plan_step_count_matches_steps() -> None:
    from famulix.plan_dsl import Plan, PlanStep

    plan = Plan(
        plan_id="test",
        steps=[
            PlanStep(id="a", tool="echo"),
            PlanStep(id="b", tool="echo"),
            PlanStep(id="c", tool="add"),
        ],
    )
    assert plan.step_count() == 3
    assert plan.step_count() == len(plan.steps)


def test_plan_tools_used_collects_unique_tools() -> None:
    from famulix.plan_dsl import Plan, PlanStep

    plan = Plan(
        plan_id="test",
        steps=[
            PlanStep(id="a", tool="echo"),
            PlanStep(id="b", tool="echo"),
            PlanStep(id="c", tool="add"),
            PlanStep(id="d", tool="echo"),
        ],
    )
    tools = plan.tools_used()
    assert tools == {"echo", "add"}
    assert len(tools) == 2


def test_check_step_types_passes_with_matching_types() -> None:
    from famulix.plan_dsl import Plan, PlanStep, check_step_types

    plan = Plan(
        plan_id="test",
        steps=[
            PlanStep(
                id="producer",
                tool="fetch",
                output_types={"data": "string"},
            ),
            PlanStep(
                id="consumer",
                tool="process",
                depends_on=["producer"],
                input_types={"data": "string"},
            ),
        ],
    )
    errors = check_step_types(plan)
    assert errors == []


def test_check_step_types_detects_mismatch() -> None:
    from famulix.plan_dsl import Plan, PlanStep, check_step_types

    plan = Plan(
        plan_id="test",
        steps=[
            PlanStep(
                id="producer",
                tool="fetch",
                output_types={"data": "string"},
            ),
            PlanStep(
                id="consumer",
                tool="process",
                depends_on=["producer"],
                input_types={"data": "integer"},
            ),
        ],
    )
    errors = check_step_types(plan)
    assert len(errors) == 1
    assert "expects integer" in errors[0]
    assert "provides string" in errors[0]


def test_check_step_types_detects_missing_provider() -> None:
    from famulix.plan_dsl import Plan, PlanStep, check_step_types

    plan = Plan(
        plan_id="test",
        steps=[
            PlanStep(
                id="producer",
                tool="fetch",
                output_types={"result": "string"},
            ),
            PlanStep(
                id="consumer",
                tool="process",
                depends_on=["producer"],
                input_types={"data": "string"},
            ),
        ],
    )
    errors = check_step_types(plan)
    assert len(errors) == 1
    assert "no provider" in errors[0]


def test_validate_plan_rejects_empty_plan_id() -> None:
    from famulix.plan_dsl import Plan, validate_plan

    plan = Plan(plan_id="")
    result = validate_plan(plan)
    assert not result.valid
    assert any("empty" in e for e in result.errors)


def test_validate_plan_rejects_duplicate_step_ids() -> None:
    from famulix.plan_dsl import Plan, PlanStep, validate_plan

    plan = Plan(
        plan_id="test",
        steps=[
            PlanStep(id="s1", tool="echo"),
            PlanStep(id="s1", tool="add"),
        ],
    )
    result = validate_plan(plan)
    assert not result.valid
    assert any("duplicate" in e for e in result.errors)


def test_validate_plan_detects_cycles() -> None:
    from famulix.plan_dsl import Plan, PlanStep, validate_plan

    plan = Plan(
        plan_id="test",
        steps=[
            PlanStep(id="s1", tool="echo", depends_on=["s2"]),
            PlanStep(id="s2", tool="echo", depends_on=["s1"]),
        ],
    )
    result = validate_plan(plan)
    assert not result.valid
    assert any("cycle" in e for e in result.errors)


def test_topological_order_respects_dependencies() -> None:
    from famulix.plan_dsl import Plan, PlanStep, topological_order

    plan = Plan(
        plan_id="test",
        steps=[
            PlanStep(id="c", tool="echo", depends_on=["b"]),
            PlanStep(id="a", tool="echo"),
            PlanStep(id="b", tool="echo", depends_on=["a"]),
        ],
    )
    order = topological_order(plan)
    assert order.index("a") < order.index("b")
    assert order.index("b") < order.index("c")


def test_plan_diff_detects_added_removed_modified() -> None:
    from famulix.plan_dsl import Plan, PlanStep, plan_diff

    plan_a = Plan(
        plan_id="test",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "old"}),
            PlanStep(id="s2", tool="add"),
        ],
    )
    plan_b = Plan(
        plan_id="test",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "new"}),
            PlanStep(id="s3", tool="multiply"),
        ],
    )
    diff = plan_diff(plan_a, plan_b)
    assert "s3" in diff["added"]
    assert "s2" in diff["removed"]
    assert "s1" in diff["modified"]


def test_plan_total_step_budget() -> None:
    from famulix.plan_dsl import Plan, PlanStep

    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="t1", budget=10.0),
            PlanStep(id="s2", tool="t2", budget=20.0),
            PlanStep(id="s3", tool="t3", budget=5.0),
        ],
    )
    assert plan.total_step_budget() == 35.0


def test_plan_budget_validation_rejects_negative_max_budget() -> None:
    from famulix.plan_dsl import Plan, PlanStep, validate_plan

    plan = Plan(plan_id="p1", steps=[PlanStep(id="s1", tool="t1")], max_budget=-1.0)
    result = validate_plan(plan)
    assert not result.valid
    assert any("max_budget" in e for e in result.errors)


def test_plan_budget_validation_rejects_exceeding_budget() -> None:
    from famulix.plan_dsl import Plan, PlanStep, validate_plan

    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="t1", budget=50.0),
            PlanStep(id="s2", tool="t2", budget=60.0),
        ],
        max_budget=100.0,
    )
    result = validate_plan(plan)
    assert not result.valid
    assert any("exceed" in e for e in result.errors)


def test_plan_budget_validation_passes_within_budget() -> None:
    from famulix.plan_dsl import Plan, PlanStep, validate_plan

    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="t1", budget=30.0),
            PlanStep(id="s2", tool="t2", budget=40.0),
        ],
        max_budget=100.0,
    )
    result = validate_plan(plan)
    assert result.valid


def test_plan_budget_zero_means_no_cap() -> None:
    from famulix.plan_dsl import Plan, PlanStep, validate_plan

    plan = Plan(
        plan_id="p1",
        steps=[PlanStep(id="s1", tool="t1", budget=1000.0)],
        max_budget=0.0,
    )
    result = validate_plan(plan)
    assert result.valid
