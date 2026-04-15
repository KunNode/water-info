"""Notification planning node."""

from __future__ import annotations

import json

from app.plan import build_notifications
from app.services.llm import get_llm
from app.state import NotificationRecord, RiskLevel
from app.state import to_plain_data
from app.utils.json_parser import extract_json


async def notification_node(state: dict) -> dict:
    assessment = state.get("risk_assessment")
    level = assessment.risk_level.value if assessment else RiskLevel.LOW.value
    plan = state.get("emergency_plan")
    plan_id = getattr(plan, "plan_id", "EP-UNKNOWN")
    notifications = [
        NotificationRecord(
            target=item["target"],
            channel=item["channel"],
            content=item["content"],
            status=item.get("status", "pending"),
        )
        for item in build_notifications(level, plan_id)
    ]

    llm = get_llm()
    message = f"已生成 {len(notifications)} 条通知"
    if llm.is_enabled:
        try:
            response = await llm.ainvoke(
                json.dumps({
                    "user_query": state.get("user_query", ""),
                    "risk_assessment": to_plain_data(assessment),
                    "plan": to_plain_data(plan),
                    "fallback_notifications": to_plain_data(notifications),
                }, ensure_ascii=False, indent=2),
                system_prompt=(
                    "你是防汛通知智能体。"
                    "请输出严格 JSON 数组，每项包含 target, channel, content, status。"
                    "通知对象和通知内容需要和当前风险等级及预案相匹配。"
                ),
                temperature=0.2,
            )
            content = getattr(response, "content", "")
            parsed = extract_json(content, expect_array=True)
            if isinstance(parsed, list) and parsed:
                notifications = [
                    NotificationRecord(
                        target=str(item.get("target", "")),
                        channel=str(item.get("channel", "sms")),
                        content=str(item.get("content", "")),
                        status=str(item.get("status", "pending")),
                    )
                    for item in parsed
                    if item.get("target") and item.get("content")
                ] or notifications
                message = f"已生成 {len(notifications)} 条通知"
        except Exception:
            message = f"已生成 {len(notifications)} 条通知"

    return {
        "notifications": notifications,
        "current_agent": "notification",
        "messages": [{"role": "notification", "content": message}],
    }
