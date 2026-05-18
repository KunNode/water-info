"""Parallel validation node.

Runs plan_reviewer and safety_checker concurrently after plan generation.
"""

from __future__ import annotations

import asyncio

from loguru import logger

from app.agents.plan_reviewer import plan_reviewer_node
from app.agents.safety_checker import safety_checker_node
from app.state import FloodResponseState
from app.utils.timeout import with_timeout


@with_timeout(180)
async def validation_parallel_node(state: FloodResponseState) -> dict:
    """Run plan_reviewer and safety_checker concurrently."""
    logger.info("Starting parallel plan validation")

    tasks = {
        "review": asyncio.create_task(plan_reviewer_node(state)),
        "safety": asyncio.create_task(safety_checker_node(state)),
    }

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    names = list(tasks.keys())

    merged: dict = {
        "current_agent": "validation_parallel",
        "messages": [{"role": "validation_parallel", "content": "并行校验完成"}],
    }

    for name, result in zip(names, results):
        if isinstance(result, Exception):
            logger.warning(f"{name} parallel execution failed: {result}")
        elif isinstance(result, dict):
            for key, value in result.items():
                if key == "messages":
                    merged.setdefault("messages", []).extend(value)
                elif key not in merged or not merged[key]:
                    merged[key] = value

    logger.info("Parallel validation complete")
    return merged
