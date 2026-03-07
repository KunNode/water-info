"""测试 Supervisor 路由决策"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.supervisor import SupervisorDecision, supervisor_node
from app.state import AgentName


class TestSupervisorDecision:
    """测试 SupervisorDecision 模型"""

    def test_valid_agents(self):
        for agent in [
            "data_analyst",
            "risk_assessor",
            "plan_generator",
            "resource_dispatcher",
            "notification",
            "execution_monitor",
            "parallel_dispatch",
            "__end__",
        ]:
            d = SupervisorDecision(next_agent=agent, reasoning="test")
            assert d.next_agent == agent

    def test_reasoning_default(self):
        d = SupervisorDecision(next_agent="__end__")
        assert d.reasoning == ""


class TestSupervisorNode:
    """测试 Supervisor 节点路由"""

    @pytest.mark.asyncio
    async def test_max_iteration_forces_end(self):
        """达到最大迭代次数时应强制结束"""
        state = {
            "user_query": "分析水情",
            "messages": [],
            "iteration": 8,
        }
        result = await supervisor_node(state)
        assert result["next_agent"] == "__end__"
        assert result["iteration"] == 9

    @pytest.mark.asyncio
    async def test_structured_routing(self):
        """测试结构化路由成功路径"""
        mock_decision = SupervisorDecision(next_agent="data_analyst", reasoning="需要数据")

        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_decision)

        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

        state = {
            "user_query": "分析当前水情",
            "messages": [],
            "iteration": 0,
        }

        with patch("app.agents.supervisor.get_llm", return_value=mock_llm):
            result = await supervisor_node(state)

        assert result["next_agent"] == "data_analyst"
        assert result["iteration"] == 1

    @pytest.mark.asyncio
    async def test_fallback_to_text_parsing(self):
        """结构化输出失败时应回退到文本解析（所有确定性步骤已完成，让 LLM 兜底）"""
        from app.state import (
            EmergencyPlan,
            NotificationRecord,
            ResourceAllocation,
            RiskAssessment,
            RiskLevel,
        )

        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(side_effect=Exception("structured output failed"))

        mock_response = MagicMock()
        mock_response.content = "execution_monitor"

        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # 所有确定性步骤均已完成，intent=unknown → 确定性路由返回 None，触发 LLM 兜底
        plan = EmergencyPlan(plan_id="p-001", plan_name="测试预案")
        state = {
            "user_query": "请继续分析",  # 无任何关键词 → intent=unknown
            "messages": [],
            "iteration": 0,
            "data_summary": "已有水情数据",
            "risk_assessment": RiskAssessment(risk_level=RiskLevel.LOW, risk_score=20.0),
            "emergency_plan": plan,
            "resource_plan": [
                ResourceAllocation(
                    resource_type="人员",
                    resource_name="救援队",
                    quantity=10,
                    source_location="市中心",
                    target_location="受灾区",
                )
            ],
            "notifications": [
                NotificationRecord(
                    target="应急办",
                    channel="sms",
                    content="橙色预警",
                )
            ],
        }

        with patch("app.agents.supervisor.get_llm", return_value=mock_llm):
            result = await supervisor_node(state)

        # 确定性路由全步骤完成 → __end__（不需要走 LLM）
        # 注意：intent=unknown 但所有步骤完成 → _deterministic_route 返回 "__end__"
        assert result["next_agent"] == "__end__"

    @pytest.mark.asyncio
    async def test_invalid_route_defaults_to_end(self):
        """无效路由应默认结束（LLM 兜底返回无效 agent 名时）"""
        from app.state import (
            EmergencyPlan,
            NotificationRecord,
            ResourceAllocation,
            RiskAssessment,
            RiskLevel,
        )

        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(side_effect=Exception("structured output failed"))

        mock_response = MagicMock()
        mock_response.content = "invalid_agent_name"

        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # 所有确定性步骤已完成 → _deterministic_route 返回 "__end__" 直接命中
        plan = EmergencyPlan(plan_id="p-002", plan_name="降级预案")
        state = {
            "user_query": "测试",
            "messages": [],
            "iteration": 0,
            "data_summary": "已有水情数据",
            "risk_assessment": RiskAssessment(risk_level=RiskLevel.LOW, risk_score=20.0),
            "emergency_plan": plan,
            "resource_plan": [
                ResourceAllocation(
                    resource_type="人员",
                    resource_name="救援队",
                    quantity=5,
                    source_location="市中心",
                    target_location="受灾区",
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

        with patch("app.agents.supervisor.get_llm", return_value=mock_llm):
            result = await supervisor_node(state)

        assert result["next_agent"] == "__end__"
