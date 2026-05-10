"""Resource dispatcher node that queries inventory and persists dispatch orders."""

from __future__ import annotations

import json
from typing import Any

from app.config import get_settings
from app.platform.dispatch_state_machine import DispatchState
from app.platform.dispatch_validator import validate_dispatch_plan
from app.services.llm import get_llm
from app.state import ResourceAllocation, to_plain_data
from app.tools.resource_tools import create_dispatch_orders, query_available_resources
from app.tools.trace import TracedCall, make_trace
from app.utils.json_parser import extract_json


async def resource_dispatcher_node(state: dict) -> dict:
    traces: list[dict] = [
        make_trace(phase="resource_dispatch", status="started", title="开始资源调度"),
    ]

    plan = state.get("emergency_plan")
    plan_resources = _coerce_allocations(getattr(plan, "resources", [])) if plan else []

    available: list[dict[str, Any]] = []
    inventory_query_failed = False
    with TracedCall(
        phase="tool_call",
        tool_name="query_available_resources",
        title="查询可用资源库存",
    ) as trace:
        try:
            result_str = await query_available_resources.ainvoke({})
            parsed = json.loads(result_str) if isinstance(result_str, str) else result_str
            available = parsed.get("data", []) if isinstance(parsed, dict) else parsed
            if not isinstance(available, list):
                available = []
            trace.complete(output_summary=f"{len(available)} 项可用资源")
        except Exception as exc:
            available = []
            inventory_query_failed = True
            trace.trace["status"] = "failed"
            trace.trace["detail"] = f"库存查询失败，已按预案资源需求降级生成调度建议：{str(exc)[:160]}"
    traces.append(trace.trace)

    resources = _match_plan_resources(plan_resources, available)
    if not resources:
        resources = plan_resources or [
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
    if inventory_query_failed:
        message += "（库存接口异常，已使用预案资源需求降级生成）"
    if llm.is_enabled and available:
        refined = await _refine_with_llm(state, plan, available, resources)
        if refined:
            resources = refined
            message = f"已制定 {len(resources)} 项资源调度安排（库存优化）"

    dispatch_orders: list[dict] = []
    if get_settings().dispatch_state_machine_enabled and available:
        validation = await validate_dispatch_plan(
            [
                {
                    "resource_id": resource.resource_id,
                    "quantity": resource.quantity,
                    "status": resource.status,
                    "source_location": resource.source_location,
                    "target_location": resource.target_location,
                }
                for resource in resources
                if resource.resource_id
            ],
            _InventoryAdapter(available),
        )
        valid_ids = {item.resource_id for item in validation.valid_allocations}
        resources = [resource for resource in resources if not resource.resource_id or resource.resource_id in valid_ids]
        dispatch_orders = [
            {
                "resource_id": item.resource_id,
                "quantity": item.quantity,
                "source_location": item.source_location,
                "target_location": item.target_location,
                "state": DispatchState.AI_DRAFT.value,
                "history": [],
            }
            for item in validation.valid_allocations
        ]
        if validation.rejected_allocations:
            traces.append(make_trace(
                phase="resource_dispatch",
                status="completed",
                title=f"已拒绝 {len(validation.rejected_allocations)} 项无效调度候选",
                metadata={"rejected_allocations": [item.model_dump(mode="json") for item in validation.rejected_allocations]},
            ))

    dispatches_to_create = [
        {
            "resource_id": resource.resource_id,
            "quantity": resource.quantity,
            "from_location": resource.source_location,
            "to_location": resource.target_location,
            "plan_id": getattr(plan, "plan_id", None),
        }
        for resource in resources
        if resource.resource_id
    ]

    if dispatches_to_create:
        with TracedCall(
            phase="tool_call",
            tool_name="create_dispatch_orders",
            title="创建资源调度单",
        ) as trace:
            result_str = await create_dispatch_orders.ainvoke({"dispatches": dispatches_to_create})
            try:
                dispatch_results = json.loads(result_str) if isinstance(result_str, str) else result_str
                if not isinstance(dispatch_results, list):
                    dispatch_results = []
                dispatch_map = {
                    item.get("resource_id"): item.get("dispatch_id")
                    for item in dispatch_results
                    if item.get("success") and item.get("dispatch_id")
                }
                for resource in resources:
                    if resource.resource_id and resource.resource_id in dispatch_map:
                        resource.dispatch_id = dispatch_map[resource.resource_id]
                success_count = sum(1 for item in dispatch_results if item.get("success"))
                trace.complete(output_summary=f"{success_count}/{len(dispatches_to_create)} 调度单创建成功")
            except (json.JSONDecodeError, TypeError):
                trace.complete(output_summary="调度单结果解析失败")
        traces.append(trace.trace)

    traces.append(make_trace(
        phase="resource_dispatch",
        status="completed",
        title=f"资源调度完成: {len(resources)} 项",
    ))

    return {
        "resource_plan": resources,
        "dispatch_orders": dispatch_orders,
        "current_agent": "resource_dispatcher",
        "messages": [{"role": "resource_dispatcher", "content": message}],
        "execution_traces": traces,
    }


class _InventoryAdapter:
    def __init__(self, resources: list[dict[str, Any]]):
        self._resources = {str(item.get("id")): item for item in resources if item.get("id")}
        self._locations = {str(item.get("location")) for item in resources if item.get("location")}

    async def get_resource(self, resource_id: str) -> dict[str, Any] | None:
        resource = self._resources.get(resource_id)
        if resource and "status" not in resource:
            return {**resource, "status": "available"}
        return resource

    async def is_known_location(self, location: str) -> bool:
        return bool(location)


def _coerce_allocations(items: list[Any]) -> list[ResourceAllocation]:
    allocations: list[ResourceAllocation] = []
    for item in items:
        if isinstance(item, ResourceAllocation):
            allocations.append(item)
            continue
        if isinstance(item, dict):
            allocations.append(ResourceAllocation(
                resource_type=str(item.get("resource_type", item.get("type", ""))),
                resource_name=str(item.get("resource_name", item.get("name", ""))),
                quantity=int(item.get("quantity", 0)),
                source_location=str(item.get("source_location", "")),
                target_location=str(item.get("target_location", "")),
                eta_minutes=int(item["eta_minutes"]) if item.get("eta_minutes") is not None else None,
                status=str(item.get("status", "pending")),
                resource_id=item.get("resource_id"),
                dispatch_id=item.get("dispatch_id"),
            ))
    return allocations


def _match_plan_resources(plan_resources: list[ResourceAllocation], available: list[dict[str, Any]]) -> list[ResourceAllocation]:
    resources: list[ResourceAllocation] = []
    for planned in plan_resources:
        matched = _find_inventory_match(planned, available)
        if not matched:
            continue
        available_quantity = int(matched.get("quantity", 0))
        if available_quantity <= 0:
            continue
        resources.append(ResourceAllocation(
            resource_type=planned.resource_type,
            resource_name=str(matched.get("name") or planned.resource_name),
            quantity=min(planned.quantity, available_quantity),
            source_location=str(matched.get("location") or planned.source_location),
            target_location=planned.target_location,
            eta_minutes=planned.eta_minutes,
            resource_id=matched.get("id"),
        ))
    return resources


def _find_inventory_match(planned: ResourceAllocation, available: list[dict[str, Any]]) -> dict[str, Any] | None:
    planned_name = planned.resource_name.lower()
    planned_type = planned.resource_type.lower()
    for item in available:
        name = str(item.get("name", "")).lower()
        resource_type = str(item.get("type", "")).lower()
        if name and (name in planned_name or planned_name in name):
            return item
        if planned_type and planned_type in resource_type:
            return item
    return None


async def _refine_with_llm(
    state: dict,
    plan: Any,
    available: list[dict[str, Any]],
    resources: list[ResourceAllocation],
) -> list[ResourceAllocation]:
    llm = get_llm()
    try:
        response = await llm.ainvoke(
            json.dumps({
                "user_query": state.get("user_query", ""),
                "risk_assessment": to_plain_data(state.get("risk_assessment")),
                "plan": to_plain_data(plan),
                "available_resources": available,
                "matched_resources": to_plain_data(resources),
            }, ensure_ascii=False, indent=2),
            system_prompt=(
                "你是防汛资源调度智能体。根据可用资源库存和预案需求，优化调度方案。"
                "请输出严格 JSON 数组，每项包含 resource_type, resource_name, quantity, "
                "source_location, target_location, eta_minutes, resource_id。resource_id 必须来自可用资源。"
                "调度数量不得超过可用库存。"
            ),
            temperature=0.2,
        )
        parsed = extract_json(getattr(response, "content", ""), expect_array=True)
    except Exception:
        return []

    available_by_id = {str(item.get("id")): item for item in available if item.get("id")}
    refined: list[ResourceAllocation] = []
    if not isinstance(parsed, list):
        return refined

    for item in parsed:
        resource_id = str(item.get("resource_id") or "")
        inventory = available_by_id.get(resource_id)
        if not inventory:
            continue
        quantity = max(0, int(item.get("quantity", 0)))
        available_quantity = int(inventory.get("quantity", 0))
        if quantity == 0 or quantity > available_quantity:
            continue
        refined.append(ResourceAllocation(
            resource_type=str(item.get("resource_type") or inventory.get("type", "")),
            resource_name=str(item.get("resource_name") or inventory.get("name", "")),
            quantity=quantity,
            source_location=str(item.get("source_location") or inventory.get("location", "")),
            target_location=str(item.get("target_location", "")),
            eta_minutes=int(item["eta_minutes"]) if item.get("eta_minutes") is not None else None,
            resource_id=resource_id,
        ))
    return refined
