"""Tests for final response aggregation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.agents.final_response import final_response_node
from app.state import EmergencyAction, EmergencyPlan, Evidence, RiskAssessment, RiskLevel


@pytest.mark.asyncio
async def test_final_response_uses_only_available_sections():
    with patch("app.agents.final_response.get_llm", return_value=SimpleNamespace(is_enabled=False)):
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
    with patch("app.agents.final_response.get_llm", return_value=SimpleNamespace(is_enabled=False)):
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


@pytest.mark.asyncio
async def test_final_response_uses_upstream_draft_without_llm_rewrite():
    with patch("app.agents.final_response.get_llm", return_value=SimpleNamespace(is_enabled=False)):
        result = await final_response_node(
            {
                "intent": "general_chat",
                "user_query": "你好",
                "final_response_draft": "你好，我是防汛 AI 助手。",
            }
        )

    assert result["final_response"] == "你好，我是防汛 AI 助手。"


@pytest.mark.asyncio
async def test_final_response_appends_evidence_once_when_using_draft():
    evidence = [
        Evidence(citation_id="[1]", content="片段A", document_title="手册"),
    ]
    with patch("app.agents.final_response.get_llm", return_value=SimpleNamespace(is_enabled=False)):
        result = await final_response_node(
            {
                "intent": "general_chat",
                "final_response_draft": "我先从知识库里找到了几段最相关的依据。",
                "evidence": evidence,
            }
        )

    final_text = result["final_response"]
    assert final_text.count("## 证据片段") == 1
    assert "片段A" in final_text


@pytest.mark.asyncio
async def test_final_response_does_not_duplicate_evidence_when_already_present():
    evidence = [
        Evidence(citation_id="[1]", content="片段A", document_title="手册"),
    ]
    draft_with_evidence = "回复主体。\n\n## 证据片段\n- [1] 片段A"
    with patch("app.agents.final_response.get_llm", return_value=SimpleNamespace(is_enabled=False)):
        result = await final_response_node(
            {
                "intent": "general_chat",
                "final_response_draft": draft_with_evidence,
                "evidence": evidence,
            }
        )

    assert result["final_response"].count("## 证据片段") == 1


@pytest.mark.asyncio
async def test_final_response_falls_back_when_validation_fails_without_llm():
    actions = [
        EmergencyAction(action_id="A-001", action_type="patrol", description="巡查"),
    ]
    plan = EmergencyPlan(plan_id="EP-001", plan_name="城区防汛预案", actions=actions)
    with patch("app.agents.final_response.get_llm", return_value=SimpleNamespace(is_enabled=False)):
        result = await final_response_node(
            {
                "intent": "plan_generation",
                "emergency_plan": plan,
                # Draft text deliberately omits the plan name and miscounts measures.
                "final_response_draft": "我们已经准备好了 共 9 项措施。",
            }
        )

    final_text = result["final_response"]
    # The deterministic fallback (built from state) names the plan correctly.
    assert "城区防汛预案" in final_text
