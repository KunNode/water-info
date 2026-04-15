"""并行调度节点

同时执行资源调度和通知智能体，减少串行等待时间。
"""

from __future__ import annotations

import asyncio

from loguru import logger

from app.agents.notification_agent import notification_node
from app.agents.resource_dispatcher import resource_dispatcher_node
from app.state import FloodResponseState
from app.utils.timeout import with_timeout


@with_timeout(180)
async def parallel_dispatch_node(state: FloodResponseState) -> dict:
    """并行执行资源调度和通知方案生成"""
    logger.info("开始并行执行资源调度和通知方案")

    resource_task = asyncio.create_task(resource_dispatcher_node(state))
    notification_task = asyncio.create_task(notification_node(state))

    results = await asyncio.gather(resource_task, notification_task, return_exceptions=True)

    merged: dict = {
        "current_agent": "parallel_dispatch",
        "messages": [{"role": "parallel_dispatch", "content": "并行调度完成"}],
    }

    # 合并资源调度结果
    resource_result = results[0]
    if isinstance(resource_result, Exception):
        logger.warning(f"资源调度并行执行失败: {resource_result}")
    elif isinstance(resource_result, dict):
        if "resource_plan" in resource_result:
            merged["resource_plan"] = resource_result["resource_plan"]
        merged["messages"].extend(resource_result.get("messages", []))

    # 合并通知方案结果
    notification_result = results[1]
    if isinstance(notification_result, Exception):
        logger.warning(f"通知方案并行执行失败: {notification_result}")
    elif isinstance(notification_result, dict):
        if "notifications" in notification_result:
            merged["notifications"] = notification_result["notifications"]
        merged["messages"].extend(notification_result.get("messages", []))

    logger.info("并行调度完成")
    return merged
