"""Execution monitor node."""

from __future__ import annotations


async def execution_monitor_node(state: dict) -> dict:
    return {
        "current_agent": "execution_monitor",
        "messages": [{"role": "execution_monitor", "content": "当前预案尚未进入自动执行阶段。"}],
        "next_agent": "__end__",
    }
