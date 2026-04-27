"""Resource dispatcher node."""

from __future__ import annotations

import json

from app.services.llm import get_llm
from app.state import ResourceAllocation, to_plain_data
from app.utils.json_parser import extract_json


async def resource_dispatcher_node(state: dict) -> dict:
    plan = state.get("emergency_plan")
    resources = list(getattr(plan, "resources", [])) if plan else []
    if not resources:
        resources = [
            ResourceAllocation(
                resource_type="人员",
                resource_name="抢险队",
                quantity=12,
                source_location="市级应急仓库",
                target_location="城区河段",
                eta_minutes=30,
            )
        ]

    llm = get_llm()
    message = f"已制定 {len(resources)} 项资源调度安排"
    if llm.is_enabled:
        try:
            response = await llm.ainvoke(
                json.dumps({
                    "user_query": state.get("user_query", ""),
                    "risk_assessment": to_plain_data(state.get("risk_assessment")),
                    "plan": to_plain_data(plan),
                    "fallback_resources": to_plain_data(resources),
                }, ensure_ascii=False, indent=2),
                system_prompt=(
                    "你是防汛资源调度智能体。"
                    "请输出严格 JSON 数组，每项包含 resource_type, resource_name, quantity, source_location, target_location, eta_minutes。"
                    "调度方案要与当前防汛预案匹配。"
                ),
                temperature=0.2,
            )
            content = getattr(response, "content", "")
            parsed = extract_json(content, expect_array=True)
            if isinstance(parsed, list) and parsed:
                resources = [
                    ResourceAllocation(
                        resource_type=str(item.get("resource_type", "")),
                        resource_name=str(item.get("resource_name", "")),
                        quantity=int(item.get("quantity", 0)),
                        source_location=str(item.get("source_location", "应急物资仓库")),
                        target_location=str(item.get("target_location", "重点防汛区域")),
                        eta_minutes=int(item["eta_minutes"]) if item.get("eta_minutes") is not None else None,
                    )
                    for item in parsed
                    if item.get("resource_type") and item.get("resource_name")
                ] or resources
                message = f"已制定 {len(resources)} 项资源调度安排"
        except Exception:
            message = f"已制定 {len(resources)} 项资源调度安排"

    return {
        "resource_plan": resources,
        "current_agent": "resource_dispatcher",
        "messages": [{"role": "resource_dispatcher", "content": message}],
    }
