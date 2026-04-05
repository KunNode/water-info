"""Combined dispatch node — runs resource_dispatcher and notification in true parallel."""

from __future__ import annotations

import asyncio

from app.agents.notification import notification_node
from app.agents.resource_dispatcher import resource_dispatcher_node


async def parallel_dispatch_node(state: dict) -> dict:
    resource_update, notification_update = await asyncio.gather(
        resource_dispatcher_node(state),
        notification_node(state),
    )
    return {
        "resource_plan": resource_update.get("resource_plan", []),
        "notifications": notification_update.get("notifications", []),
        "current_agent": "parallel_dispatch",
        "messages": [{"role": "parallel_dispatch", "content": "已并行完成资源调度与通知方案生成。"}],
    }
