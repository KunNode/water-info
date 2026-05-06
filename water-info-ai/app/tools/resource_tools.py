"""Resource management tools for the resource dispatcher agent."""

from __future__ import annotations

import json

from app.services.platform_client import get_platform_client
from app.tools.simple_tool import SimpleTool


async def _query_available_resources(payload: dict) -> str:
    resource_type = str(payload.get("resource_type", ""))
    location = str(payload.get("location", ""))
    client = get_platform_client()
    result = await client.get_available_resources(
        resource_type=resource_type,
        location=location,
    )
    resources = result.get("data", [])
    return json.dumps(resources, ensure_ascii=False)


async def _create_dispatch_orders(payload: dict) -> str:
    dispatches = payload.get("dispatches", [])
    if not dispatches:
        return json.dumps({"error": "dispatches list is empty"}, ensure_ascii=False)

    client = get_platform_client()
    results = []
    for dispatch in dispatches:
        try:
            result = await client.create_dispatch_order({
                "resourceId": dispatch.get("resource_id", ""),
                "quantity": int(dispatch.get("quantity", 0)),
                "fromLocation": dispatch.get("from_location", ""),
                "toLocation": dispatch.get("to_location", ""),
                "planId": dispatch.get("plan_id"),
                "source": "AI",
                "notes": dispatch.get("notes"),
            })
            data = result.get("data", {})
            results.append({
                "dispatch_id": data.get("id", ""),
                "resource_id": data.get("resourceId", ""),
                "status": data.get("status", ""),
                "success": True,
            })
        except Exception as exc:
            results.append({
                "resource_id": dispatch.get("resource_id", ""),
                "success": False,
                "error": str(exc)[:200],
            })

    return json.dumps(results, ensure_ascii=False)


query_available_resources = SimpleTool("query_available_resources", _query_available_resources)
create_dispatch_orders = SimpleTool("create_dispatch_orders", _create_dispatch_orders)

resource_tools = [
    query_available_resources,
    create_dispatch_orders,
]
