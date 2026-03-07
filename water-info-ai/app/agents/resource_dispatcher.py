"""资源调度智能体

根据应急预案的措施清单，制定具体的人员、物资、设备调度方案。
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.services.llm import get_llm
from app.state import FloodResponseState, ResourceAllocation
from app.utils.timeout import with_timeout

RESOURCE_DISPATCHER_PROMPT = """你是防洪应急预案系统的 **资源调度智能体**。

你的职责：
1. 根据应急预案中的措施清单，制定详细的资源调度方案
2. 确定每项措施所需的人员、物资、设备数量和来源
3. 规划调度路线和预计到达时间

输出要求（JSON数组格式）：
[
    {
        "resource_type": "人员|设备|物资|车辆",
        "resource_name": "资源名称",
        "quantity": 数量,
        "source_location": "调出地点",
        "target_location": "调往地点",
        "eta_minutes": 预计到达时间(分钟)
    }
]

注意：
- 就近调配原则，优先从最近的仓库/驻地调集
- 考虑道路通行条件和天气影响
- 关键资源（如冲锋舟、挖掘机）需标注备用方案
- 人员调度要考虑换班轮休
"""


@with_timeout(120)
async def resource_dispatcher_node(state: FloodResponseState) -> dict:
    """资源调度节点"""
    llm = get_llm()

    plan = state.get("emergency_plan")
    risk = state.get("risk_assessment")

    plan_info = ""
    if plan and plan.actions:
        actions_str = "\n".join(
            f"- [{a.priority}级] {a.action_type}: {a.description} (责任: {a.responsible_dept})"
            for a in plan.actions
        )
        plan_info = f"预案: {plan.plan_name}\n响应等级: {plan.risk_level.value}\n措施清单:\n{actions_str}"
    else:
        plan_info = "暂无预案措施，请制定基础防汛资源调度方案"

    risk_info = ""
    if risk:
        risk_info = f"风险等级: {risk.risk_level.value}, 受影响站点: {', '.join(risk.affected_stations)}"

    messages = [
        SystemMessage(content=RESOURCE_DISPATCHER_PROMPT),
        HumanMessage(content=f"""请根据以下预案制定资源调度方案：

## 预案信息
{plan_info}

## 风险情况
{risk_info}

请制定详细的资源调度方案，输出JSON数组格式。"""),
    ]

    response = await llm.ainvoke(messages)
    final_message = response.content
    logger.info(f"资源调度完成: {final_message[:200]}")

    # 解析资源调度方案
    from app.utils.json_parser import extract_json
    resource_plan: list[ResourceAllocation] = []
    resources_data = extract_json(final_message, expect_array=True)
    if resources_data and isinstance(resources_data, list):
        try:
            for r in resources_data:
                resource_plan.append(ResourceAllocation(
                    resource_type=r.get("resource_type", "物资"),
                    resource_name=r.get("resource_name", ""),
                    quantity=r.get("quantity", 0),
                    source_location=r.get("source_location", ""),
                    target_location=r.get("target_location", ""),
                    eta_minutes=r.get("eta_minutes"),
                ))
        except (ValueError, KeyError) as e:
            logger.warning(f"解析资源调度方案失败: {e}")

    return {
        "resource_plan": resource_plan,
        "current_agent": "resource_dispatcher",
        "messages": [{"role": "resource_dispatcher", "content": final_message}],
    }
