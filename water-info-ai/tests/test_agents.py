"""Smoke tests for agent nodes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.data_analyst import data_analyst_node
from app.agents.plan_generator import plan_generator_node
from app.agents.risk_assessor import risk_assessor_node
from app.agents.supervisor import supervisor_node
from app.state import EmergencyPlan, RiskAssessment, RiskLevel


class TestSupervisorNode:
    @pytest.mark.asyncio
    async def test_routes_data_query_to_data_analyst(self):
        result = await supervisor_node(
            {
                "session_id": "test-session",
                "user_query": "分析当前水情数据",
                "messages": [],
                "iteration": 0,
            }
        )

        assert result["next_agent"] == "data_analyst"
        assert result["iteration"] == 1

    @pytest.mark.asyncio
    async def test_routes_risk_query_to_risk_assessor_after_data_is_ready(self):
        result = await supervisor_node(
            {
                "session_id": "test-session",
                "user_query": "评估当前洪水风险",
                "messages": [],
                "iteration": 0,
                "data_summary": "已有水情摘要",
            }
        )

        assert result["next_agent"] == "risk_assessor"

    @pytest.mark.asyncio
    async def test_routes_completed_workflow_to_end(self):
        result = await supervisor_node(
            {
                "session_id": "test-session",
                "user_query": "请继续",
                "messages": [],
                "iteration": 0,
                "data_summary": "已有水情摘要",
                "risk_assessment": RiskAssessment(risk_level=RiskLevel.LOW, risk_score=20.0),
                "emergency_plan": EmergencyPlan(plan_id="plan-1", plan_name="测试预案"),
                "resource_plan": [{"resource_name": "抢险队"}],
                "notifications": [{"target": "应急办"}],
            }
        )

        assert result["next_agent"] == "__end__"


class TestAgentNodes:
    @pytest.mark.asyncio
    async def test_data_analyst_node_returns_summary(self):
        with patch(
            "app.agents.data_analyst._build_deterministic_bundle",
            AsyncMock(return_value={"data_summary": "数据分析完成"}),
        ):
            result = await data_analyst_node(
                {
                    "session_id": "test-session",
                    "user_query": "分析当前水情",
                    "messages": [],
                    "iteration": 0,
                }
            )

        assert result["data_summary"] == "数据分析完成"
        assert result["current_agent"] == "data_analyst"

    @pytest.mark.asyncio
    async def test_data_analyst_node_falls_back_to_llm_when_deterministic_summary_fails(self):
        mock_agent = SimpleNamespace(
            ainvoke=AsyncMock(return_value={"messages": [SimpleNamespace(content="LLM 数据分析完成")]})
        )

        with (
            patch(
                "app.agents.data_analyst._build_deterministic_bundle",
                AsyncMock(side_effect=RuntimeError("db failed")),
            ),
            patch("app.agents.data_analyst.create_react_agent", return_value=mock_agent),
        ):
            result = await data_analyst_node(
                {
                    "session_id": "test-session",
                    "user_query": "分析当前水情",
                    "messages": [],
                    "iteration": 0,
                }
            )

        assert result["data_summary"] == "LLM 数据分析完成"

    @pytest.mark.asyncio
    async def test_risk_assessor_node_parses_json_payload(self):
        mock_agent = SimpleNamespace(
            ainvoke=AsyncMock(
                return_value={
                    "messages": [
                        SimpleNamespace(
                            content='{"risk_level":"high","risk_score":76.5,"affected_stations":["S1"],"key_risks":["水位持续上涨"],"trend":"rising","reasoning":"达到高风险阈值"}'
                        )
                    ]
                }
            )
        )

        with patch("app.agents.risk_assessor.create_react_agent", return_value=mock_agent):
            result = await risk_assessor_node(
                {
                    "session_id": "test-session",
                    "user_query": "评估风险",
                    "messages": [],
                    "iteration": 0,
                    "data_summary": "站点 S1 水位持续上涨",
                }
            )

        assert result["risk_assessment"].risk_level == RiskLevel.HIGH
        assert result["risk_assessment"].risk_score == 76.5

    @pytest.mark.asyncio
    async def test_risk_assessor_node_uses_deterministic_path_when_structured_data_exists(self):
        result = await risk_assessor_node(
            {
                "session_id": "test-session",
                "user_query": "评估风险",
                "messages": [],
                "iteration": 0,
                "overview_data": {
                    "stations": [
                        {
                            "id": "station-1",
                            "code": "S1",
                            "name": "站点一",
                            "water_level": 3.6,
                            "warning_level": 3.0,
                            "danger_level": 3.5,
                            "rainfall": 35.0,
                            "rainfall_warning": 30.0,
                            "rainfall_danger": 50.0,
                        }
                    ],
                    "active_alarms": [
                        {"station_id": "station-1", "station_name": "站点一", "message": "水位告警"}
                    ],
                },
                "weather_forecast": {"forecast": {"total_precip_24h_mm": 60.0}},
            }
        )

        assert result["risk_assessment"].risk_level in {RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL}
        assert result["risk_assessment"].risk_score > 0

    @pytest.mark.asyncio
    async def test_plan_generator_node_builds_draft_plan(self):
        result = await plan_generator_node(
            {
                "session_id": "test-session",
                "user_query": "生成应急预案",
                "messages": [],
                "iteration": 0,
                "data_summary": "多个站点接近警戒水位",
                "risk_assessment": RiskAssessment(
                    risk_level=RiskLevel.HIGH,
                    risk_score=80.0,
                    affected_stations=["S1"],
                    key_risks=["水位超过警戒线"],
                ),
            }
        )

        assert result["emergency_plan"].plan_id.startswith("EP-")
        assert result["emergency_plan"].actions[0].action_type != ""
