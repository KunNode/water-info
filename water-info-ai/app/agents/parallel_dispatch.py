"""Combined dispatch node used as a placeholder for parallel fan-out."""

from __future__ import annotations

from app.agents.notification import notification_node
from app.agents.resource_dispatcher import resource_dispatcher_node


async def parallel_dispatch_node(state: dict) -> dict:
    resource_update = await resource_dispatcher_node(state)
    notification_update = await notification_node({**state, **resource_update})
    return {
        "resource_plan": resource_update.get("resource_plan", []),
        "notifications": notification_update.get("notifications", []),
        "current_agent": "parallel_dispatch",
        "messages": [{"role": "parallel_dispatch", "content": "已并行完成资源调度与通知方案生成。"}],
    }
