"""Structured output and routing tests for the platform kernel."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_agent_output_models_validate_required_shapes():
    from app.schemas.agent_outputs import (
        ExecutionMonitorOutput,
        PlanGeneratorOutput,
        ResourceDispatcherOutput,
        RiskAssessorOutput,
    )
    from app.state import RiskLevel

    risk = RiskAssessorOutput(
        risk_level=RiskLevel.MODERATE,
        risk_score=0.6,
        affected_stations=["ST001"],
        response_level="III",
        reasoning="水位上涨",
    )
    plan = PlanGeneratorOutput(
        actions=[{"action_id": "a1"}],
        resources=[{"resource_id": "r1"}],
        notifications=[{"target": "值班室"}],
        trigger_conditions="水位超警",
    )
    dispatch = ResourceDispatcherOutput(
        resource_plan=[
            {
                "resource_id": "r1",
                "quantity": 2,
                "status": "candidate",
                "source_location": "warehouse",
                "target_location": "station-a",
            }
        ]
    )
    monitor = ExecutionMonitorOutput(progress_pct=42.5)

    assert risk.risk_score == 0.6
    assert plan.trigger_conditions == "水位超警"
    assert dispatch.resource_plan[0].quantity == 2
    assert monitor.blocked_actions == []


@pytest.mark.asyncio
async def test_output_validator_returns_graceful_failure_for_invalid_payload():
    from app.platform.output_validator import validate_agent_output

    result = await validate_agent_output(
        "risk_assessor",
        {
            "risk_level": "high",
            "risk_score": 1.5,
            "affected_stations": [],
            "response_level": "II",
            "reasoning": "invalid score",
        },
    )

    assert result.valid is False
    assert result.validated_output is None
    assert result.raw_output["risk_score"] == 1.5
    assert result.errors


@pytest.mark.asyncio
async def test_supervisor_structured_routing_enabled_sets_decision(monkeypatch):
    from app.agents.supervisor import supervisor_node
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("STRUCTURED_OUTPUT_ENABLED", "true")
    mock_llm = SimpleNamespace(is_enabled=False, ainvoke=AsyncMock())

    with patch("app.agents.supervisor.get_llm", return_value=mock_llm):
        result = await supervisor_node(
            {
                "user_query": "请生成防汛应急预案",
                "messages": [],
                "iteration": 0,
            }
        )

    assert result["agent_run_id"]
    assert result["routing_decision"]["next_agent"] == result["next_agent"]
    assert result["safety_level"] in {"normal", "elevated", "high", "critical"}
    assert result["human_confirmation_required"] is False


@pytest.mark.asyncio
async def test_supervisor_uses_skill_sequence_when_registry_enabled(monkeypatch):
    from app.agents.supervisor import supervisor_node
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("SKILL_REGISTRY_ENABLED", "true")
    mock_llm = SimpleNamespace(is_enabled=False, ainvoke=AsyncMock())

    with patch("app.agents.supervisor.get_llm", return_value=mock_llm):
        result = await supervisor_node(
            {
                "user_query": "请做风险研判",
                "intent": "risk_assessment",
                "messages": [],
                "iteration": 0,
            }
        )

    assert result["active_skill_id"] == "risk_assessment"
    assert result["skill_agent_sequence"] == ["data_analyst", "risk_assessor"]
    assert "query_station_data" in result["allowed_tools"]
    assert result["next_agent"] == "data_analyst"
