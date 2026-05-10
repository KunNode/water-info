"""Focused tests for platform kernel component primitives."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_metadata_filter_validates_enums_and_expiry_matching():
    from app.rag.models import MetadataFilter, SearchResult, metadata_matches_filter

    metadata_filter = MetadataFilter(doc_type="regulation", authority_level="municipal", region_code="510000")
    active = SearchResult(
        chunk_id="c1",
        document_id="d1",
        document_title="规程",
        source_uri="",
        content="content",
        metadata={
            "doc_type": "regulation",
            "authority_level": "municipal",
            "region_code": "510000",
            "expire_date": (datetime.now(UTC) + timedelta(days=1)).date().isoformat(),
        },
    )
    expired = SearchResult(
        chunk_id="c2",
        document_id="d2",
        document_title="过期规程",
        source_uri="",
        content="content",
        metadata={
            "doc_type": "regulation",
            "authority_level": "municipal",
            "region_code": "510000",
            "expire_date": (datetime.now(UTC) - timedelta(days=1)).date().isoformat(),
        },
    )

    assert metadata_matches_filter(active, metadata_filter) is True
    assert metadata_matches_filter(expired, metadata_filter) is False

    with pytest.raises(ValueError):
        MetadataFilter(doc_type="invalid")


@pytest.mark.asyncio
async def test_plan_reviewer_and_safety_checker_default_off_degrade(monkeypatch):
    from app.agents.plan_reviewer import plan_reviewer_node
    from app.agents.safety_checker import safety_checker_node
    from app.config import get_settings
    from app.state import EmergencyAction, EmergencyPlan

    get_settings.cache_clear()
    monkeypatch.delenv("PLAN_REVIEWER_ENABLED", raising=False)

    plan = EmergencyPlan(
        plan_id="p1",
        plan_name="测试预案",
        actions=[EmergencyAction(action_id="a1", action_type="evacuation", description="组织撤离")],
    )

    reviewed = await plan_reviewer_node({"emergency_plan": plan})
    checked = await safety_checker_node({"emergency_plan": plan})

    assert reviewed["compliance_result"]["compliant"] is True
    assert reviewed["compliance_result"]["status"] == "skipped"
    assert checked["safety_check_result"]["safe_to_proceed"] is False
    assert checked["pending_approvals"]


def test_skill_registry_loads_core_skills_and_quality_gates():
    from app.platform.skill_registry import SkillRegistry

    registry = SkillRegistry()
    registry.load_all()

    skill = registry.lookup_by_intent("risk_assessment")

    assert skill is not None
    assert skill.id == "risk_assessment"
    assert registry.lookup_by_intent("missing_intent") is None


@pytest.mark.asyncio
async def test_skill_executor_runs_sequence_and_evaluates_gate():
    from app.platform.skill_executor import SkillExecutor
    from app.skills.schema import QualityGate, SkillDefinition

    async def first(state):
        return {"risk_assessment": {"risk_score": 0.7}}

    skill = SkillDefinition(
        id="s1",
        name="测试技能",
        version="1.0",
        trigger_intents=["test"],
        required_inputs=["user_query"],
        required_tools=[],
        agent_sequence=["first"],
        output_schema="RiskAssessorOutput",
        quality_gates=[
            QualityGate(
                name="risk_score_present",
                check_type="field_present",
                target_field="risk_assessment.risk_score",
                condition="is_not_none",
            )
        ],
        fallback_strategy="degrade",
    )

    state, result = await SkillExecutor().execute(skill, {"user_query": "x"}, {"first": first})

    assert state["risk_assessment"]["risk_score"] == 0.7
    assert result.quality_results[0].passed is True


@pytest.mark.asyncio
async def test_dispatch_validator_state_machine_and_hil():
    from app.platform.dispatch_state_machine import DispatchState, DispatchStateMachine, InvalidTransitionError
    from app.platform.dispatch_validator import validate_dispatch_plan
    from app.platform.human_in_the_loop import (
        ApprovalDecision,
        HumanInTheLoopGateway,
        PendingApproval,
    )

    class Inventory:
        async def get_resource(self, resource_id):
            return {"id": resource_id, "quantity": 5, "status": "available", "location": "warehouse"}

        async def is_known_location(self, location):
            return location == "station-a"

    validation = await validate_dispatch_plan(
        [
            {
                "resource_id": "r1",
                "quantity": 3,
                "status": "candidate",
                "source_location": "warehouse",
                "target_location": "station-a",
            },
            {
                "resource_id": "r2",
                "quantity": 9,
                "status": "candidate",
                "source_location": "warehouse",
                "target_location": "unknown",
            },
        ],
        Inventory(),
    )
    assert len(validation.valid_allocations) == 1
    assert len(validation.rejected_allocations) == 1

    machine = DispatchStateMachine()
    record = machine.transition(DispatchState.APPROVED, operator_id="u1", reason="同意")
    assert record.from_state == DispatchState.AI_DRAFT
    with pytest.raises(InvalidTransitionError):
        machine.transition(DispatchState.RETURNED, operator_id="u1", reason="invalid")

    gateway = HumanInTheLoopGateway()
    approval_id = await gateway.submit_for_approval(
        PendingApproval(action_type="dispatch_approval", action_payload={"id": "d1"}, evidence=[])
    )
    await gateway.approve(
        approval_id,
        ApprovalDecision(approved=True, approver_id="leader", reason="ok"),
    )
    assert gateway.get(approval_id).status == "approved"


@pytest.mark.asyncio
async def test_audit_recorder_noops_when_disabled_and_buffers_failures():
    from app.platform.audit_models import AgentRunRecord
    from app.platform.audit_recorder import AuditRecorder

    class Client:
        async def post_audit_record(self, *_args, **_kwargs):
            raise RuntimeError("missing table")

    record = AgentRunRecord(
        session_id="s1",
        agent_run_id="run1",
        agent_name="supervisor",
        input_state_json={},
        status="started",
    )
    disabled = AuditRecorder(Client(), enabled=False)
    enabled = AuditRecorder(Client(), enabled=True, buffer_limit=2)

    await disabled.record_agent_run(record)
    await enabled.record_agent_run(record)

    assert disabled.buffer == []
    assert len(enabled.buffer) == 1
