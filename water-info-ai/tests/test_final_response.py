"""Tests for final response aggregation."""

from __future__ import annotations

import pytest

from app.agents.final_response import final_response_node
from app.state import EmergencyAction, EmergencyPlan, RiskAssessment, RiskLevel


@pytest.mark.asyncio
async def test_final_response_uses_only_available_sections():
    result = await final_response_node(
        {
            "user_query": "分析当前水情数据",
            "data_summary": "## 总览\n- 监测站点 6 个\n- 活跃告警 3 条",
        }
    )

    final_text = result["final_response"]
    assert "监测站点 6 个" in final_text
    assert "监测站点 6 个" in final_text
    assert "风险等级" not in final_text


@pytest.mark.asyncio
async def test_final_response_includes_error_and_plan_details():
    result = await final_response_node(
        {
            "data_summary": "数据摘要",
            "risk_assessment": RiskAssessment(
                risk_level=RiskLevel.HIGH,
                risk_score=80.0,
                key_risks=["持续强降雨"],
            ),
            "emergency_plan": EmergencyPlan(
                plan_id="EP-001",
                plan_name="城区防汛预案",
                actions=[
                    EmergencyAction(
                        action_id="A-001",
                        action_type="patrol",
                        description="加密巡查",
                        priority=1,
                        responsible_dept="防汛办",
                    )
                ],
                summary="立即响应",
            ),
            "intent": "plan_generation",
            "error": "data_analyst_node timed out after 120s",
        }
    )

    final_text = result["final_response"]
    assert "high" in final_text
    assert "城区防汛预案" in final_text
    assert "timed out after 120s" in final_text
