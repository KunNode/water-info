"""执行监控智能体

监控应急预案的执行进度，汇总各项措施的完成情况，
发现问题并提出调整建议。
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.services.llm import get_llm
from app.state import ExecutionProgress, FloodResponseState
from app.utils.timeout import with_timeout

EXECUTION_MONITOR_PROMPT = """你是防洪应急预案系统的 **执行监控智能体**。

你的职责：
1. 监控预案中各项措施的执行进度
2. 识别执行中的问题和风险
3. 提出调整建议

请基于当前掌握的信息，评估预案执行情况并给出监控报告。

输出要求（JSON格式）：
{
    "total_actions": 总措施数,
    "completed_actions": 已完成数,
    "in_progress_actions": 执行中数,
    "failed_actions": 失败数,
    "progress_pct": 完成百分比,
    "issues": ["发现的问题列表"],
    "recommendations": ["建议列表"]
}
"""


@with_timeout(120)
async def execution_monitor_node(state: FloodResponseState) -> dict:
    """执行监控节点"""
    llm = get_llm()

    plan = state.get("emergency_plan")
    resource_plan = state.get("resource_plan", [])
    notifications = state.get("notifications", [])

    context_parts = []
    if plan and plan.actions:
        actions_summary = "\n".join(
            f"- {a.action_id}: [{a.status}] {a.description}"
            for a in plan.actions
        )
        context_parts.append(f"预案措施:\n{actions_summary}")

    if resource_plan:
        context_parts.append(f"资源调度: 共{len(resource_plan)}项调度任务")

    if notifications:
        context_parts.append(f"通知: 共{len(notifications)}条通知，"
                           f"已发送{sum(1 for n in notifications if n.status == 'sent')}条")

    messages = [
        SystemMessage(content=EXECUTION_MONITOR_PROMPT),
        HumanMessage(content=f"""请评估当前预案执行情况：

{chr(10).join(context_parts) if context_parts else '当前没有正在执行的预案'}

请给出执行监控报告。"""),
    ]

    response = await llm.ainvoke(messages)
    final_message = response.content
    logger.info(f"执行监控完成: {final_message[:200]}")

    from app.utils.json_parser import extract_json
    progress_data = extract_json(final_message)
    if progress_data and isinstance(progress_data, dict):
        try:
            progress = ExecutionProgress(
                total_actions=progress_data.get("total_actions", 0),
                completed_actions=progress_data.get("completed_actions", 0),
                in_progress_actions=progress_data.get("in_progress_actions", 0),
                failed_actions=progress_data.get("failed_actions", 0),
                progress_pct=progress_data.get("progress_pct", 0.0),
                issues=progress_data.get("issues", []),
                recommendations=progress_data.get("recommendations", []),
            )
        except (ValueError, KeyError):
            progress = ExecutionProgress()
    else:
        progress = ExecutionProgress()

    return {
        "execution_progress": progress,
        "current_agent": "execution_monitor",
        "messages": [{"role": "execution_monitor", "content": final_message}],
    }
