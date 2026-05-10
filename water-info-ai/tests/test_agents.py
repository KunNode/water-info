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
                "user_query": "当前水情整体情况怎么样",
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

    @pytest.mark.asyncio
    async def test_does_not_repeat_risk_assessor_after_risk_is_ready(self):
        mock_llm = SimpleNamespace(
            is_enabled=True,
            ainvoke=AsyncMock(
                return_value=SimpleNamespace(
                    content='{"next_agent":"risk_assessor","intent":"risk_assessment","focus_station_query":null,"reasoning":"继续评估风险"}'
                )
            ),
        )

        with patch("app.agents.supervisor.get_llm", return_value=mock_llm):
            result = await supervisor_node(
                {
                    "session_id": "test-session",
                    "user_query": "评估当前洪水风险",
                    "messages": [],
                    "iteration": 2,
                    "data_summary": "已有水情摘要",
                    "risk_assessment": RiskAssessment(risk_level=RiskLevel.HIGH, risk_score=76.4),
                }
            )

        assert result["next_agent"] == "__end__"
        mock_llm.ainvoke.assert_not_awaited()


class TestAgentNodes:
    @pytest.mark.asyncio
    async def test_data_analyst_node_returns_summary(self):
        with (
            patch(
                "app.agents.data_analyst._build_deterministic_bundle",
                AsyncMock(
                    return_value={
                        "data_summary": "数据分析完成",
                        "overview_data": {"stations": [], "active_alarms": [], "station_count": 0, "alarm_count": 0},
                        "weather_forecast": {"forecast": {"total_precip_24h_mm": 0}},
                    }
                ),
            ),
            patch("app.agents.data_analyst.get_llm", return_value=SimpleNamespace(is_enabled=False)),
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
    async def test_data_analyst_data_only_station_query_returns_recent_observation_table(self):
        db = SimpleNamespace(
            get_recent_observations=AsyncMock(
                return_value=[
                    {
                        "observed_at": "2026-05-02T12:30:00+08:00",
                        "metric_type": "WATER_LEVEL",
                        "value": 4.248,
                        "unit": "m",
                        "quality_flag": "GOOD",
                    },
                    {
                        "observed_at": "2026-05-02T12:25:00+08:00",
                        "metric_type": "WATER_LEVEL",
                        "value": 4.220,
                        "unit": "m",
                        "quality_flag": "GOOD",
                    },
                ]
            )
        )
        with (
            patch(
                "app.agents.data_analyst._build_deterministic_bundle",
                AsyncMock(
                    return_value={
                        "data_summary": "默认摘要",
                        "overview_data": {
                            "stations": [
                                {
                                    "id": "station-1",
                                    "code": "ST_NORTH",
                                    "name": "北闸站",
                                    "water_level": 4.248,
                                }
                            ],
                            "active_alarms": [],
                            "station_count": 1,
                            "alarm_count": 0,
                        },
                        "weather_forecast": {"forecast": {"total_precip_24h_mm": 0}},
                    }
                ),
            ),
            patch("app.agents.data_analyst.get_llm", return_value=SimpleNamespace(is_enabled=False)),
            patch("app.agents.data_analyst.get_db_service", return_value=db),
        ):
            result = await data_analyst_node(
                {
                    "session_id": "test-session",
                    "user_query": "北闸站最新5条水位数据，无需分析",
                    "answer_policy": {
                        "data_only": True,
                        "requested_count": 5,
                        "metric_type": "WATER_LEVEL",
                    },
                }
            )

        summary = result["data_summary"]
        assert "北闸站" in summary
        assert "| 时间 | 指标 | 数值 | 单位 | 质量 |" in summary
        assert "4.248" in summary
        assert "当前库内仅查到 2 条" in summary
        db.get_recent_observations.assert_awaited_once_with(
            station_id="station-1",
            metric_type="WATER_LEVEL",
            limit=5,
        )

    @pytest.mark.asyncio
    async def test_data_analyst_node_falls_back_to_llm_when_deterministic_summary_fails(self):
        mock_llm = SimpleNamespace(
            is_enabled=True,
            ainvoke=AsyncMock(return_value=SimpleNamespace(content="LLM 数据分析完成")),
        )

        with (
            patch(
                "app.agents.data_analyst._build_deterministic_bundle",
                AsyncMock(side_effect=RuntimeError("db failed")),
            ),
            patch("app.agents.data_analyst.get_llm", return_value=mock_llm),
        ):
            with pytest.raises(RuntimeError):
                await data_analyst_node(
                    {
                        "session_id": "test-session",
                        "user_query": "分析当前水情",
                        "messages": [],
                        "iteration": 0,
                    }
                )

        mock_llm.ainvoke.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_risk_assessor_node_parses_json_payload(self):
        mock_llm = SimpleNamespace(
            is_enabled=True,
            ainvoke=AsyncMock(
                return_value=SimpleNamespace(
                    content='{"risk_level":"high","risk_score":76.5,"affected_stations":["S1"],"key_risks":["水位持续上涨"],"trend":"rising","reasoning":"达到高风险阈值"}'
                )
            ),
        )

        with patch("app.agents.risk_assessor.get_llm", return_value=mock_llm):
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
                            }
                        ],
                        "active_alarms": [],
                    },
                    "weather_forecast": {"forecast": {"total_precip_24h_mm": 20.0}},
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
    async def test_risk_assessor_node_guards_model_understatement(self):
        mock_llm = SimpleNamespace(
            is_enabled=True,
            ainvoke=AsyncMock(
                return_value=SimpleNamespace(
                    content='{"risk_level":"none","risk_score":1,"affected_stations":[],"key_risks":[],"trend":"stable","reasoning":"模型低估"}'
                )
            ),
        )

        with patch("app.agents.risk_assessor.get_llm", return_value=mock_llm):
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
                                "water_level": 3.8,
                                "warning_level": 3.0,
                                "danger_level": 3.5,
                                "rainfall": 45.0,
                            }
                        ],
                        "active_alarms": [
                            {"station_id": "station-1", "station_name": "站点一", "message": "水位告警"}
                        ],
                    },
                    "weather_forecast": {"forecast": {"total_precip_24h_mm": 80.0}},
                }
            )

        assert result["risk_assessment"].risk_level in {RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL}
        assert result["risk_assessment"].risk_score >= 40
        assert "保守上调" in "；".join(result["risk_assessment"].key_risks)

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

    @pytest.mark.asyncio
    async def test_plan_generator_node_falls_back_when_model_payload_is_incomplete(self):
        mock_llm = SimpleNamespace(
            is_enabled=True,
            ainvoke=AsyncMock(
                return_value=SimpleNamespace(
                    content='{"plan_name":"空预案","trigger_conditions":"无","summary":"无","actions":[],"resources":[],"notifications":[],"citations":[]}'
                )
            ),
        )

        with patch("app.agents.plan_generator.get_llm", return_value=mock_llm):
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

        assert result["emergency_plan"].plan_name != "空预案"
        assert result["emergency_plan"].actions[0].action_type != ""

    @pytest.mark.asyncio
    async def test_plan_generator_node_falls_back_when_model_payload_has_extra_fields(self):
        mock_llm = SimpleNamespace(
            is_enabled=True,
            ainvoke=AsyncMock(
                return_value=SimpleNamespace(
                    content=(
                        '{"plan_name":"越界预案","trigger_conditions":"高风险","summary":"响应",'
                        '"actions":[{"action_type":"patrol","description":"巡查","priority":1,'
                        '"responsible_dept":"防汛办","deadline_minutes":30,"unexpected":"extra"}],'
                        '"resources":[{"resource_type":"team","resource_name":"抢险队","quantity":1,'
                        '"source_location":"仓库","target_location":"城区","eta_minutes":20}],'
                        '"notifications":[],"citations":[]}'
                    )
                )
            ),
        )

        with patch("app.agents.plan_generator.get_llm", return_value=mock_llm):
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

        assert result["emergency_plan"].plan_name != "越界预案"
        assert result["emergency_plan"].actions[0].action_type != ""

    @pytest.mark.asyncio
    async def test_plan_generator_node_accepts_harness_valid_payload(self):
        mock_llm = SimpleNamespace(
            is_enabled=True,
            ainvoke=AsyncMock(
                return_value=SimpleNamespace(
                    content=(
                        '{"plan_name":"城区高风险防汛预案","trigger_conditions":"水位超过警戒线",'
                        '"summary":"立即组织重点区域巡查和物资前置。",'
                        '"actions":[{"action_type":"patrol","description":"加密巡查低洼路段",'
                        '"priority":1,"responsible_dept":"防汛办","deadline_minutes":30}],'
                        '"resources":[{"resource_type":"team","resource_name":"抢险队","quantity":2,'
                        '"source_location":"应急仓库","target_location":"低洼片区","eta_minutes":20}],'
                        '"notifications":[{"target":"街道值班员","channel":"sms","content":"请立即到岗",'
                        '"status":"pending"}],'
                        '"citations":[{"citation_id":"[1]","document_title":"防汛手册",'
                        '"source_uri":"kb://manual","content":"高风险响应条款"}]}'
                    )
                )
            ),
        )

        with patch("app.agents.plan_generator.get_llm", return_value=mock_llm):
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

        plan = result["emergency_plan"]
        assert plan.plan_name == "城区高风险防汛预案"
        assert plan.actions[0].responsible_dept == "防汛办"
        assert plan.resources[0].quantity == 2
        assert plan.notifications[0].target == "街道值班员"
        assert plan.citations[0]["citation_id"] == "[1]"
