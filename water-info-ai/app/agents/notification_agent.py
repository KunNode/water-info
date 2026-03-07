"""通知智能体

制定预警通知方案，确定通知渠道、内容和目标人群。
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.services.llm import get_llm
from app.state import FloodResponseState, NotificationRecord
from app.utils.timeout import with_timeout

NOTIFICATION_PROMPT = """你是防洪应急预案系统的 **通知智能体**。

你的职责：
1. 根据风险等级和预案内容，制定预警通知方案
2. 确定不同渠道（短信/微信/广播/邮件）的通知内容
3. 明确通知目标人群和优先级

通知渠道说明：
- sms: 短信通知 — 用于紧急通知领导和关键人员
- wechat: 微信/企业微信 — 用于工作群组通知
- broadcast: 应急广播 — 用于向公众发布预警
- email: 邮件 — 用于正式通知和报告

输出要求（JSON数组格式）：
[
    {
        "target": "通知目标(人员/部门/公众群体)",
        "channel": "sms|wechat|broadcast|email",
        "content": "通知内容(200字以内)",
        "status": "pending"
    }
]

注意：
- 不同等级通知范围不同：低风险仅通知值班人员，极高风险需全媒体发布
- 通知内容要简洁明确，包含关键信息（风险等级、影响范围、响应要求）
- 面向公众的通知要通俗易懂，避免专业术语
"""


@with_timeout(120)
async def notification_node(state: FloodResponseState) -> dict:
    """通知智能体节点"""
    llm = get_llm()

    risk = state.get("risk_assessment")
    plan = state.get("emergency_plan")

    context_parts = []
    if risk:
        context_parts.append(
            f"风险等级: {risk.risk_level.value}\n"
            f"风险分数: {risk.risk_score}\n"
            f"受影响站点: {', '.join(risk.affected_stations)}\n"
            f"关键风险: {'; '.join(risk.key_risks)}"
        )
    if plan:
        context_parts.append(
            f"预案名称: {plan.plan_name}\n"
            f"预案概述: {plan.summary}\n"
            f"通知目标: {', '.join(plan.notification_targets)}"
        )

    messages = [
        SystemMessage(content=NOTIFICATION_PROMPT),
        HumanMessage(content=f"""请制定预警通知方案：

{chr(10).join(context_parts) if context_parts else '请制定基础防汛值班通知'}

请输出JSON数组格式的通知方案。"""),
    ]

    response = await llm.ainvoke(messages)
    final_message = response.content
    logger.info(f"通知方案完成: {final_message[:200]}")

    from app.utils.json_parser import extract_json
    notifications: list[NotificationRecord] = []
    notif_data = extract_json(final_message, expect_array=True)
    if notif_data and isinstance(notif_data, list):
        try:
            for n in notif_data:
                notifications.append(NotificationRecord(
                    target=n.get("target", ""),
                    channel=n.get("channel", "sms"),
                    content=n.get("content", ""),
                    status=n.get("status", "pending"),
                ))
        except (ValueError, KeyError) as e:
            logger.warning(f"解析通知方案失败: {e}")

    return {
        "notifications": notifications,
        "current_agent": "notification",
        "messages": [{"role": "notification", "content": final_message}],
    }
