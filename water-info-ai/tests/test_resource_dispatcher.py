"""Tests for resource dispatcher resilience."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.resource_dispatcher import resource_dispatcher_node
from app.state import EmergencyPlan, ResourceAllocation


@pytest.mark.asyncio
async def test_resource_dispatcher_degrades_when_inventory_query_fails():
    plan = EmergencyPlan(
        plan_id="EP-RESOURCE-FALLBACK",
        plan_name="资源降级测试预案",
        resources=[
            ResourceAllocation(
                resource_type="人员",
                resource_name="抢险队",
                quantity=12,
                source_location="市级应急仓库",
                target_location="翠屏湖心站",
                eta_minutes=30,
            )
        ],
    )

    with patch(
        "app.agents.resource_dispatcher.query_available_resources.ainvoke",
        new=AsyncMock(side_effect=RuntimeError("platform 500")),
    ), patch(
        "app.agents.resource_dispatcher.get_llm",
        return_value=SimpleNamespace(is_enabled=False),
    ):
        result = await resource_dispatcher_node({"emergency_plan": plan})

    assert len(result["resource_plan"]) == 1
    assert result["resource_plan"][0].resource_name == "抢险队"
    assert "降级生成" in result["messages"][0]["content"]
    inventory_trace = next(
        trace for trace in result["execution_traces"]
        if trace.get("tool_name") == "query_available_resources"
    )
    assert inventory_trace["status"] == "failed"
    assert "库存查询失败" in inventory_trace["detail"]
