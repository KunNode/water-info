"""Plan generator agent."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from loguru import logger

from app.services.llm import get_creative_llm
from app.state import EmergencyAction, EmergencyPlan, FloodResponseState, PlanStatus, ResourceAllocation, RiskLevel
from app.tools.plan_tools import generate_plan_id, get_response_template, lookup_emergency_contacts, plan_generation_tools
from app.utils.json_parser import extract_json
from app.utils.timeout import with_timeout

PLAN_GENERATOR_PROMPT = """你是防汛应急预案系统的预案生成智能体。
请结合风险评估、模板和联系人信息，输出完整 JSON 预案。
"""


def _risk_level_value(state: FloodResponseState) -> str:
    risk = state.get("risk_assessment")
    return risk.risk_level.value if risk else RiskLevel.MODERATE.value


def _build_deterministic_plan(state: FloodResponseState) -> EmergencyPlan:
    risk = state.get("risk_assessment")
    risk_level = _risk_level_value(state)
    template = json.loads(get_response_template.invoke({"risk_level": risk_level}))
    contacts = json.loads(lookup_emergency_contacts.invoke({"risk_level": risk_level}))
    plan_id = generate_plan_id.invoke({})

    affected_area = (
        ", ".join(risk.affected_stations[:3])
        if risk and risk.affected_stations
        else "重点防汛区域"
    )

    actions = [
        EmergencyAction(
            action_id=f"A-{index:03d}",
            action_type=item.get("type", "general"),
            description=item.get("desc", ""),
            priority=int(item.get("priority", 3)),
            responsible_dept=template.get("command_center", ""),
            deadline_minutes=max(15, int(item.get("priority", 3)) * 15),
        )
        for index, item in enumerate(template.get("actions", []), start=1)
    ]

    resources = [
        ResourceAllocation(
            resource_type=item.get("type", "物资"),
            resource_name=item.get("name", ""),
            quantity=int(item.get("quantity", 0)),
            source_location="市级防汛物资仓库",
            target_location=affected_area,
            eta_minutes=30 if risk_level in {"low", "moderate"} else 20,
        )
        for item in template.get("resources", [])
    ]

    top_risks = "；".join((risk.key_risks[:3] if risk else [])) or "根据当前监测数据动态调整"
    notification_targets = [item.get("dept", "") for item in contacts if item.get("dept")]

    return EmergencyPlan(
        plan_id=plan_id,
        plan_name=f"{template.get('response_level', 'III级响应')}防汛应急预案",
        risk_level=risk.risk_level if risk else RiskLevel.MODERATE,
        trigger_conditions=top_risks,
        actions=actions,
        resources=resources,
        notification_targets=notification_targets,
        status=PlanStatus.DRAFT,
        summary=(
            f"面向 {affected_area} 启动 {template.get('response_level', 'III级响应')}，"
            f"由 {template.get('command_center', '防汛指挥部')} 统一调度。"
        ),
    )


async def _build_llm_plan(state: FloodResponseState) -> tuple[EmergencyPlan, str]:
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
        )

    prompt = f"""请根据以下风险评估结果生成应急预案：

## 风险评估
{risk_info}

## 数据概况
{state.get('data_summary', '')[:800]}
"""

    result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
    final_message = result["messages"][-1].content if result["messages"] else ""
    plan_data = extract_json(final_message)
    if plan_data and isinstance(plan_data, dict):
        try:
            actions = [
                EmergencyAction(
                    action_id=item.get("action_id", f"A-{index:03d}"),
                    action_type=item.get("action_type", "general"),
                    description=item.get("description", ""),
                    priority=item.get("priority", 3),
                    responsible_dept=item.get("responsible_dept", ""),
                    deadline_minutes=item.get("deadline_minutes"),
                )
                for index, item in enumerate(plan_data.get("actions", []), start=1)
            ]
            plan = EmergencyPlan(
                plan_id=plan_data.get("plan_id", ""),
                plan_name=plan_data.get("plan_name", "防汛应急预案"),
                risk_level=risk.risk_level if risk else RiskLevel.MODERATE,
                trigger_conditions=plan_data.get("trigger_conditions", ""),
                actions=actions,
                notification_targets=plan_data.get("notification_targets", []),
                status=PlanStatus.DRAFT,
                summary=plan_data.get("summary", ""),
            )
            return plan, final_message
        except (ValueError, KeyError):
            pass

    return EmergencyPlan(summary=final_message), final_message


@with_timeout(120)
async def plan_generator_node(state: FloodResponseState) -> dict:
    try:
        plan = _build_deterministic_plan(state)
        logger.info(f"Deterministic plan generated: {plan.plan_id}")
        return {
            "emergency_plan": plan,
            "current_agent": "plan_generator",
            "messages": [{"role": "plan_generator", "content": plan.summary}],
        }
    except Exception as exc:
        logger.warning(f"Deterministic plan generation failed, falling back to LLM: {exc}")

    plan, final_message = await _build_llm_plan(state)
    logger.info(f"LLM plan generated: {final_message[:200]}")
    return {
        "emergency_plan": plan,
        "current_agent": "plan_generator",
        "messages": [{"role": "plan_generator", "content": final_message}],
    }
