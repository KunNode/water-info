"""Notification agent."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.services.llm import get_llm
from app.state import FloodResponseState, NotificationRecord
from app.utils.json_parser import extract_json
from app.utils.timeout import with_timeout

NOTIFICATION_PROMPT = """你是防汛应急预案系统的通知智能体。
请输出 JSON 数组格式的通知方案。
"""


def _channels_for_level(level: str) -> list[str]:
    if level == "critical":
        return ["sms", "wechat", "broadcast"]
    if level == "high":
        return ["sms", "wechat"]
    if level == "moderate":
        return ["wechat", "sms"]
    return ["wechat"]


def _build_deterministic_notifications(state: FloodResponseState) -> list[NotificationRecord]:
    risk = state.get("risk_assessment")
    plan = state.get("emergency_plan")
    level = risk.risk_level.value if risk else "moderate"
    channels = _channels_for_level(level)
    targets = plan.notification_targets if plan and plan.notification_targets else ["防汛值班中心"]
    key_risk = risk.key_risks[0] if risk and risk.key_risks else "请关注当前水情变化"
    content = (
        f"当前防汛风险等级为 {level}。{key_risk}。"
        f"{plan.summary if plan and plan.summary else '请按预案要求落实值守和处置。'}"
    )

    records: list[NotificationRecord] = []
    for index, target in enumerate(targets[: max(2, len(channels))]):
        channel = channels[min(index, len(channels) - 1)]
        records.append(
            NotificationRecord(
                target=target,
                channel=channel,
                content=content,
                status="pending",
            )
        )
    return records


@with_timeout(120)
async def notification_node(state: FloodResponseState) -> dict:
    try:
        notifications = _build_deterministic_notifications(state)
        logger.info(f"Deterministic notification plan generated: {len(notifications)} notifications")
        return {
            "notifications": notifications,
            "current_agent": "notification",
            "messages": [{"role": "notification", "content": f"生成 {len(notifications)} 条通知"}],
        }
    except Exception as exc:
        logger.warning(f"Deterministic notification generation failed, falling back to LLM: {exc}")

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
        HumanMessage(content="\n\n".join(context_parts) or "请制定基础防汛值班通知"),
    ]

    response = await llm.ainvoke(messages)
    final_message = response.content
    notifications: list[NotificationRecord] = []
    notif_data = extract_json(final_message, expect_array=True)
    if notif_data and isinstance(notif_data, list):
        for item in notif_data:
            notifications.append(
                NotificationRecord(
                    target=item.get("target", ""),
                    channel=item.get("channel", "sms"),
                    content=item.get("content", ""),
                    status=item.get("status", "pending"),
                )
            )

    return {
        "notifications": notifications,
        "current_agent": "notification",
        "messages": [{"role": "notification", "content": final_message}],
    }
