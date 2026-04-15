"""Timeout helpers for agent nodes."""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable

from loguru import logger


def with_timeout(seconds: int) -> Callable:
    """Wrap an async agent node and return a structured timeout payload."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> dict:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                func_name = func.__name__
                agent_name = func_name.removesuffix("_node")
                logger.error(f"{func_name} timed out after {seconds}s")
                return {
                    "error": f"{func_name} timed out after {seconds}s",
                    "current_agent": agent_name,
                    "messages": [{"role": agent_name, "content": f"Timed out after {seconds}s"}],
                }

        return wrapper

    return decorator
