"""Tests for final response aggregation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.final_response import final_response_node
from app.state import (
    EmergencyAction,
    EmergencyPlan,
    Evidence,
    NotificationRecord,
    ResourceAllocation,
    RiskAssessment,
    RiskLevel,
)


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


@pytest.mark.asyncio
async def test_final_response_renders_llm_json_with_stable_sections():
    mock_llm = SimpleNamespace(
        is_enabled=True,
        ainvoke=AsyncMock(
            return_value=SimpleNamespace(
                content=(
                    '{"conclusion":"当前整体风险等级为 high，建议立即加强巡查。",'
                    '"key_points":["水位超过警戒线","降雨仍在持续"],'
                    '"recommendations":["加密巡查重点站点"],'
                    '"warnings":["不要解除值守"]}'
                )
            )
        ),
    )

    with patch("app.agents.final_response.get_llm", return_value=mock_llm):
        result = await final_response_node(
            {
                "intent": "risk_assessment",
                "user_query": "评估当前风险",
                "risk_assessment": RiskAssessment(
                    risk_level=RiskLevel.HIGH,
                    risk_score=80.0,
                    key_risks=["水位超过警戒线"],
                ),
            }
        )

    final_text = result["final_response"]
    assert final_text.startswith("## 结论\n当前整体风险等级为 high")
    assert "\n\n## 要点\n- 水位超过警戒线\n- 降雨仍在持续" in final_text
    assert "\n\n## 建议\n- 加密巡查重点站点" in final_text
    assert "\n\n## 提醒\n- 不要解除值守" in final_text
    assert mock_llm.ainvoke.await_args.kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_final_response_ignores_freeform_llm_markdown_for_format_similarity():
    mock_llm = SimpleNamespace(
        is_enabled=True,
        ainvoke=AsyncMock(return_value=SimpleNamespace(content="### 自由发挥\n当前风险偏低，可以放心。")),
    )

    with patch("app.agents.final_response.get_llm", return_value=mock_llm):
        result = await final_response_node(
            {
                "intent": "risk_assessment",
                "user_query": "评估当前风险",
                "risk_assessment": RiskAssessment(
                    risk_level=RiskLevel.HIGH,
                    risk_score=80.0,
                    key_risks=["水位超过警戒线"],
                ),
            }
        )

    final_text = result["final_response"]
    assert final_text.startswith("## 结论\n我的结论是：当前整体风险等级为 **high**")
    assert "### 自由发挥" not in final_text
    assert "偏低" not in final_text


@pytest.mark.asyncio
async def test_final_response_fallback_is_repeatable_for_same_state():
    state = {
        "intent": "plan_generation",
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
    }

    with patch("app.agents.final_response.get_llm", return_value=SimpleNamespace(is_enabled=False)):
        first = await final_response_node(state)
        second = await final_response_node(state)

    assert first["final_response"] == second["final_response"]
    assert first["final_response"].split("\n\n")[:3] == [
        "## 预案概览\n- 预案名称：城区防汛预案\n- 风险等级：high\n- 触发条件：综合风险达到响应阈值\n- 预案摘要：立即响应",
        "## 处置措施\n1. [优先级 1] 加密巡查（责任：防汛办；时限：未限定）",
        "## 资源配置\n- 暂无结构化资源配置，先由应急仓库和属地队伍待命。",
    ]


@pytest.mark.asyncio
async def test_plan_generation_uses_plan_specific_stable_format_and_skips_final_llm():
    mock_llm = SimpleNamespace(
        is_enabled=True,
        ainvoke=AsyncMock(return_value=SimpleNamespace(content='{"conclusion":"不应使用"}')),
    )
    plan = EmergencyPlan(
        plan_id="EP-001",
        plan_name="城区防汛预案",
        risk_level=RiskLevel.HIGH,
        trigger_conditions="水位超过警戒线",
        summary="立即响应",
        actions=[
            EmergencyAction(
                action_id="A-001",
                action_type="patrol",
                description="加密巡查低洼路段",
                priority=1,
                responsible_dept="防汛办",
                deadline_minutes=30,
            )
        ],
        resources=[
            ResourceAllocation(
                resource_type="team",
                resource_name="抢险队",
                quantity=2,
                source_location="应急仓库",
                target_location="低洼片区",
                eta_minutes=20,
            )
        ],
        notifications=[
            NotificationRecord(
                target="街道值班员",
                channel="sms",
                content="请立即到岗",
            )
        ],
    )

    with patch("app.agents.final_response.get_llm", return_value=mock_llm):
        result = await final_response_node(
            {
                "intent": "plan_generation",
                "user_query": "生成防汛预案",
                "emergency_plan": plan,
                "risk_assessment": RiskAssessment(
                    risk_level=RiskLevel.HIGH,
                    risk_score=80.0,
                    key_risks=["水位超过警戒线"],
                ),
            }
        )

    final_text = result["final_response"]
    assert final_text.split("\n\n")[:5] == [
        "## 预案概览\n- 预案名称：城区防汛预案\n- 风险等级：high\n- 触发条件：水位超过警戒线\n- 预案摘要：立即响应",
        "## 处置措施\n1. [优先级 1] 加密巡查低洼路段（责任：防汛办；时限：30 分钟）",
        "## 资源配置\n1. 抢险队 x2（类型：team；来源：应急仓库；目标：低洼片区；到位：20 分钟）",
        "## 通知安排\n1. 街道值班员（渠道：sms；状态：pending）：请立即到岗",
        "## 执行提醒\n- 重点风险：水位超过警戒线。\n- 执行过程中需持续回看水位、雨量、告警和现场反馈，必要时升级响应。",
    ]
    mock_llm.ainvoke.assert_not_awaited()
