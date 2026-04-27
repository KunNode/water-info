"""Tests for supervisor routing decisions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.supervisor import SupervisorDecision, supervisor_node
from app.state import EmergencyPlan, NotificationRecord, ResourceAllocation, RiskAssessment, RiskLevel


class TestSupervisorDecision:
    def test_valid_agents(self):
        for agent in [
            "data_analyst",
            "risk_assessor",
            "plan_generator",
            "resource_dispatcher",
            "notification",
            "execution_monitor",
            "parallel_dispatch",
            "knowledge_retriever",
            "__end__",
        ]:
            decision = SupervisorDecision(next_agent=agent, reasoning="ok")
            assert decision.next_agent == agent

    @pytest.mark.asyncio
    async def test_routes_knowledge_query_to_knowledge_retriever(self):
        result = await supervisor_node(
            {
                "user_query": "III级响应的值班制度是什么",
                "messages": [],
                "iteration": 0,
            }
        )

        assert result["next_agent"] == "knowledge_retriever"


class TestSupervisorNode:
    @pytest.mark.asyncio
    async def test_max_iteration_forces_end(self):
        result = await supervisor_node(
            {
                "user_query": "分析水情",
                "messages": [],
                "iteration": 8,
            }
        )

        assert result["next_agent"] == "__end__"
        assert result["iteration"] == 9

    @pytest.mark.asyncio
    async def test_error_in_state_forces_end(self):
        result = await supervisor_node(
            {
                "user_query": "分析水情",
                "messages": [],
                "iteration": 1,
                "error": "data_analyst_node timed out after 120s",
            }
        )

        assert result["next_agent"] == "__end__"

    @pytest.mark.asyncio
    async def test_llm_json_fallback_is_used_for_unknown_intent(self):
        mock_llm = SimpleNamespace(
            is_enabled=True,
            ainvoke=AsyncMock(
                return_value=SimpleNamespace(
                    content='{"next_agent":"execution_monitor","reasoning":"用户在追问执行进度"}'
                )
            )
        )

        state = {
            "user_query": "执行进度现在如何",
            "messages": [],
            "iteration": 0,
            "data_summary": "已有摘要",
            "risk_assessment": RiskAssessment(risk_level=RiskLevel.LOW, risk_score=25.0),
            "emergency_plan": EmergencyPlan(plan_id="p-001", plan_name="测试预案"),
            "resource_plan": [
                ResourceAllocation(
                    resource_type="人员",
                    resource_name="抢险队",
                    quantity=10,
                    source_location="市中心",
                    target_location="城区河段",
                )
            ],
            "notifications": [],
        }

        with (
            patch("app.agents.supervisor._deterministic_route", return_value=None),
            patch("app.agents.supervisor.get_llm", return_value=mock_llm),
        ):
            result = await supervisor_node(state)

        assert result["next_agent"] == "execution_monitor"

    @pytest.mark.asyncio
    async def test_model_route_is_primary_when_safe(self):
        mock_llm = SimpleNamespace(
            is_enabled=True,
            ainvoke=AsyncMock(
                return_value=SimpleNamespace(
                    content='{"next_agent":"risk_assessor","reasoning":"用户需要进一步研判风险"}'
                )
            ),
        )

        state = {
            "user_query": "当前水情态势还需要进一步判断吗",
            "messages": [],
            "iteration": 0,
            "data_summary": "已有摘要",
        }

        with (
            patch("app.agents.supervisor._deterministic_route", return_value="__end__"),
            patch("app.agents.supervisor.get_llm", return_value=mock_llm),
        ):
            result = await supervisor_node(state)

        assert result["next_agent"] == "risk_assessor"
        mock_llm.ainvoke.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_guard_prevents_plan_before_data_and_risk_grounding(self):
        mock_llm = SimpleNamespace(
            is_enabled=True,
            ainvoke=AsyncMock(
                return_value=SimpleNamespace(
                    content='{"next_agent":"plan_generator","reasoning":"用户要求生成预案"}'
                )
            ),
        )

        state = {
            "user_query": "直接给我一份应急预案",
            "messages": [],
            "iteration": 0,
        }

        with (
            patch("app.agents.supervisor._deterministic_route", return_value="data_analyst"),
            patch("app.agents.supervisor.get_llm", return_value=mock_llm),
        ):
            result = await supervisor_node(state)

        assert result["next_agent"] == "data_analyst"
        assert "guarded" in result["supervisor_reasoning"]

    @pytest.mark.asyncio
    async def test_plain_text_fallback_defaults_to_end_when_invalid(self):
        mock_llm = SimpleNamespace(
            is_enabled=True,
            ainvoke=AsyncMock(
                side_effect=[
                    SimpleNamespace(content="not-json"),
                    SimpleNamespace(content="invalid_agent"),
                ]
            )
        )

        state = {
            "user_query": "执行情况还有哪些未完成",
            "messages": [],
            "iteration": 0,
            "data_summary": "已有摘要",
            "risk_assessment": RiskAssessment(risk_level=RiskLevel.LOW, risk_score=25.0),
            "emergency_plan": EmergencyPlan(plan_id="p-002", plan_name="测试预案"),
            "resource_plan": [
                ResourceAllocation(
                    resource_type="人员",
                    resource_name="抢险队",
                    quantity=5,
                    source_location="市中心",
                    target_location="城区河段",
                )
            ],
            "notifications": [
                NotificationRecord(
                    target="应急办",
                    channel="sms",
                    content="蓝色预警",
                )
            ],
        }

        with (
            patch("app.agents.supervisor._deterministic_route", return_value=None),
            patch("app.agents.supervisor.get_llm", return_value=mock_llm),
        ):
            result = await supervisor_node(state)

        assert result["next_agent"] == "__end__"
