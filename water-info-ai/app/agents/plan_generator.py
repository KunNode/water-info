"""预案生成智能体

根据风险评估等级，调用模板工具并结合 LLM 生成
针对性的应急响应预案。
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from loguru import logger

from app.services.llm import get_creative_llm
from app.state import (
    EmergencyAction,
    EmergencyPlan,
    FloodResponseState,
    PlanStatus,
    ResourceAllocation,
)
from app.tools.plan_tools import plan_generation_tools
from app.utils.timeout import with_timeout

PLAN_GENERATOR_PROMPT = """你是防洪应急预案系统的 **预案生成智能体**。

你的职责：
1. 根据风险评估结果确定应急响应等级
2. 调用模板工具获取标准响应模板
3. 结合实际情况生成定制化的应急预案

你拥有以下工具：
- generate_plan_id: 生成唯一预案编号
- get_response_template: 获取标准应急响应模板
- lookup_emergency_contacts: 查询应急联系人

工作流程：
1. 生成预案编号
2. 根据风险等级获取响应模板
3. 查询应急联系人
4. 基于模板和实际情况定制预案内容

输出要求（JSON格式）：
{
    "plan_id": "预案编号",
    "plan_name": "预案名称",
    "risk_level": "风险等级",
    "trigger_conditions": "触发条件描述",
    "actions": [
        {
            "action_id": "措施编号",
            "action_type": "措施类型",
            "description": "措施描述",
            "priority": 1-5,
            "responsible_dept": "责任部门",
            "deadline_minutes": 响应时限(分钟)
        }
    ],
    "notification_targets": ["通知目标列表"],
    "summary": "预案总体概述(200字以内)"
}
"""


@with_timeout(120)
async def plan_generator_node(state: FloodResponseState) -> dict:
    """预案生成节点"""
    llm = get_creative_llm()

    agent = create_react_agent(
        model=llm,
        tools=plan_generation_tools,
        prompt=PLAN_GENERATOR_PROMPT,
    )

    risk = state.get("risk_assessment")
    risk_info = ""
    if risk:
        risk_info = (
            f"风险等级: {risk.risk_level.value}\n"
            f"风险分数: {risk.risk_score}\n"
            f"受影响站点: {', '.join(risk.affected_stations)}\n"
            f"关键风险: {'; '.join(risk.key_risks)}\n"
            f"趋势: {risk.trend}\n"
            f"评估说明: {risk.reasoning[:500]}"
        )
    else:
        risk_info = "暂无风险评估数据，请基于一般性防汛要求生成预案"

    data_summary = state.get("data_summary", "")

    prompt = f"""请根据以下风险评估结果生成应急预案：

## 风险评估
{risk_info}

## 数据概况
{data_summary[:800]}

请按步骤执行：
1. 先调用 generate_plan_id 生成预案编号
2. 调用 get_response_template 获取对应等级的标准模板
3. 调用 lookup_emergency_contacts 获取联系人
4. 基于上述信息，结合实际水情生成定制化预案

输出完整的JSON格式预案。
"""

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=prompt)]
    })

    final_message = result["messages"][-1].content if result["messages"] else ""
    logger.info(f"预案生成完成: {final_message[:200]}")

    # 解析预案
    from app.utils.json_parser import extract_json
    plan_data = extract_json(final_message)
    if plan_data and isinstance(plan_data, dict):
        try:
            actions = []
            for i, a in enumerate(plan_data.get("actions", [])):
                actions.append(EmergencyAction(
                    action_id=a.get("action_id", f"A-{i+1:03d}"),
                    action_type=a.get("action_type", "general"),
                    description=a.get("description", ""),
                    priority=a.get("priority", 3),
                    responsible_dept=a.get("responsible_dept", ""),
                    deadline_minutes=a.get("deadline_minutes"),
                ))

            plan = EmergencyPlan(
                plan_id=plan_data.get("plan_id", ""),
                plan_name=plan_data.get("plan_name", "防洪应急预案"),
                risk_level=risk.risk_level if risk else "moderate",
                trigger_conditions=plan_data.get("trigger_conditions", ""),
                actions=actions,
                notification_targets=plan_data.get("notification_targets", []),
                status=PlanStatus.DRAFT,
                summary=plan_data.get("summary", ""),
            )
        except (ValueError, KeyError) as e:
            logger.warning(f"解析预案失败: {e}")
            plan = EmergencyPlan(summary=final_message)
    else:
        plan = EmergencyPlan(summary=final_message)

    return {
        "emergency_plan": plan,
        "current_agent": "plan_generator",
        "messages": [{"role": "plan_generator", "content": final_message}],
    }
