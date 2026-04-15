"""Plan generator node."""

from __future__ import annotations

import json

from app.plan import generate_plan_id, get_response_template
from app.services.llm import get_llm
from app.state import EmergencyAction, EmergencyPlan, NotificationRecord, ResourceAllocation, RiskLevel
from app.state import to_plain_data
from app.utils.json_parser import extract_json


async def plan_generator_node(state: dict) -> dict:
    assessment = state.get("risk_assessment")
    level = assessment.risk_level.value if assessment else RiskLevel.LOW.value
    level = level if level != RiskLevel.NONE.value else RiskLevel.LOW.value
    template = get_response_template(level)
    plan_id = generate_plan_id()

    actions = [
        EmergencyAction(
            action_id=f"{plan_id}-A{i + 1:02d}",
            action_type=item["type"],
            description=item["desc"],
            priority=int(item.get("priority", 3)),
            responsible_dept=template["command_center"],
        )
        for i, item in enumerate(template["actions"])
    ]
    resources = [
        ResourceAllocation(
            resource_type=item["type"],
            resource_name=item["name"],
            quantity=int(item["quantity"]),
            source_location="应急物资仓库",
            target_location="重点防汛区域",
        )
        for item in template["resources"]
    ]
    plan = EmergencyPlan(
        plan_id=plan_id,
        plan_name=f"{template['response_level']}防汛应急预案",
        risk_level=level,
        trigger_conditions="综合风险达到响应阈值",
        status="draft",
        session_id=state.get("session_id", ""),
        summary="根据当前水情和风险评估生成的应急响应草案。",
        actions=actions,
        resources=resources,
    )

    llm = get_llm()
    message = f"已生成预案 {plan.plan_name}"
    if llm.is_enabled:
        try:
            response = await llm.ainvoke(
                json.dumps({
                    "user_query": state.get("user_query", ""),
                    "risk_assessment": to_plain_data(assessment),
                    "data_summary": state.get("data_summary", ""),
                    "template_reference": template,
                    "fallback_plan": to_plain_data(plan),
                }, ensure_ascii=False, indent=2),
                system_prompt=(
                    "你是防汛应急预案生成智能体。"
                    "请基于风险评估和模板参考，输出严格 JSON。"
                    "字段必须包含：plan_name, trigger_conditions, summary, actions, resources, notifications。"
                    "actions 中每项至少包含 action_type, description, priority, responsible_dept, deadline_minutes。"
                    "resources 中每项至少包含 resource_type, resource_name, quantity, source_location, target_location, eta_minutes。"
                    "notifications 中每项至少包含 target, channel, content, status。"
                    "不得输出与防汛无关内容。"
                ),
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = getattr(response, "content", "")
            parsed = extract_json(content) or {}
            if parsed:
                plan.plan_name = str(parsed.get("plan_name") or plan.plan_name)
                plan.trigger_conditions = str(parsed.get("trigger_conditions") or plan.trigger_conditions)
                plan.summary = str(parsed.get("summary") or plan.summary)

                parsed_actions = parsed.get("actions") or []
                if isinstance(parsed_actions, list) and parsed_actions:
                    plan.actions = [
                        EmergencyAction(
                            action_id=f"{plan_id}-A{i + 1:02d}",
                            action_type=str(item.get("action_type", "")),
                            description=str(item.get("description", "")),
                            priority=int(item.get("priority", 3)),
                            responsible_dept=str(item.get("responsible_dept", template["command_center"])),
                            deadline_minutes=int(item["deadline_minutes"]) if item.get("deadline_minutes") is not None else None,
                        )
                        for i, item in enumerate(parsed_actions)
                        if item.get("action_type") and item.get("description")
                    ] or plan.actions

                parsed_resources = parsed.get("resources") or []
                if isinstance(parsed_resources, list) and parsed_resources:
                    plan.resources = [
                        ResourceAllocation(
                            resource_type=str(item.get("resource_type", "")),
                            resource_name=str(item.get("resource_name", "")),
                            quantity=int(item.get("quantity", 0)),
                            source_location=str(item.get("source_location", "应急物资仓库")),
                            target_location=str(item.get("target_location", "重点防汛区域")),
                            eta_minutes=int(item["eta_minutes"]) if item.get("eta_minutes") is not None else None,
                        )
                        for item in parsed_resources
                        if item.get("resource_type") and item.get("resource_name")
                    ] or plan.resources

                parsed_notifications = parsed.get("notifications") or []
                if isinstance(parsed_notifications, list) and parsed_notifications:
                    plan.notifications = [
                        NotificationRecord(
                            target=str(item.get("target", "")),
                            channel=str(item.get("channel", "sms")),
                            content=str(item.get("content", "")),
                            status=str(item.get("status", "pending")),
                        )
                        for item in parsed_notifications
                        if item.get("target") and item.get("content")
                    ]
                message = f"已生成预案 {plan.plan_name}，包含 {len(plan.actions)} 项措施"
        except Exception:
            message = f"已生成预案 {plan.plan_name}"

    return {
        "emergency_plan": plan,
        "current_agent": "plan_generator",
        "messages": [{"role": "plan_generator", "content": message}],
    }
