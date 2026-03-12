"""Resource dispatcher agent."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.services.llm import get_llm
from app.state import FloodResponseState, ResourceAllocation
from app.utils.json_parser import extract_json
from app.utils.timeout import with_timeout

RESOURCE_DISPATCHER_PROMPT = """你是防汛应急预案系统的资源调度智能体。
请输出 JSON 数组格式的资源调度方案。
"""


def _build_deterministic_resources(state: FloodResponseState) -> list[ResourceAllocation]:
    plan = state.get("emergency_plan")
    if plan and plan.resources:
        return plan.resources

    affected_area = "重点防汛区域"
    risk = state.get("risk_assessment")
    if risk and risk.affected_stations:
        affected_area = ", ".join(risk.affected_stations[:3])

    return [
        ResourceAllocation(
            resource_type="人员",
            resource_name="巡查队",
            quantity=8,
            source_location="防汛值班中心",
            target_location=affected_area,
            eta_minutes=25,
        )
    ]


@with_timeout(120)
async def resource_dispatcher_node(state: FloodResponseState) -> dict:
    try:
        resource_plan = _build_deterministic_resources(state)
        logger.info(f"Deterministic resource plan generated: {len(resource_plan)} resources")
        return {
            "resource_plan": resource_plan,
            "current_agent": "resource_dispatcher",
            "messages": [{"role": "resource_dispatcher", "content": f"生成 {len(resource_plan)} 项资源调度"}],
        }
    except Exception as exc:
        logger.warning(f"Deterministic resource dispatch failed, falling back to LLM: {exc}")

    llm = get_llm()
    plan = state.get("emergency_plan")
    risk = state.get("risk_assessment")

    plan_info = ""
    if plan and plan.actions:
        actions_str = "\n".join(
            f"- [{action.priority}级] {action.action_type}: {action.description}"
            for action in plan.actions
        )
        plan_info = f"预案: {plan.plan_name}\n措施清单:\n{actions_str}"

    risk_info = ""
    if risk:
        risk_info = f"风险等级: {risk.risk_level.value}, 受影响站点: {', '.join(risk.affected_stations)}"

    messages = [
        SystemMessage(content=RESOURCE_DISPATCHER_PROMPT),
        HumanMessage(content=f"{plan_info}\n\n{risk_info}"),
    ]

    response = await llm.ainvoke(messages)
    final_message = response.content
    resources_data = extract_json(final_message, expect_array=True)
    resource_plan: list[ResourceAllocation] = []
    if resources_data and isinstance(resources_data, list):
        for item in resources_data:
            resource_plan.append(
                ResourceAllocation(
                    resource_type=item.get("resource_type", "物资"),
                    resource_name=item.get("resource_name", ""),
                    quantity=item.get("quantity", 0),
                    source_location=item.get("source_location", ""),
                    target_location=item.get("target_location", ""),
                    eta_minutes=item.get("eta_minutes"),
                )
            )

    return {
        "resource_plan": resource_plan,
        "current_agent": "resource_dispatcher",
        "messages": [{"role": "resource_dispatcher", "content": final_message}],
    }
