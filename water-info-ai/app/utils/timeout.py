"""异步超时装饰器

为智能体节点提供统一的超时保护，超时后返回 error 状态而非抛出异常。
"""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable

from loguru import logger


def with_timeout(seconds: int) -> Callable:
    """异步函数超时装饰器。

    用 asyncio.wait_for 包装目标协程，超时返回包含 error 字段的 dict。

    Args:
        seconds: 超时秒数

    Usage:
        @with_timeout(120)
        async def some_agent_node(state):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> dict:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                func_name = func.__name__
                logger.error(f"{func_name} 超时（{seconds}秒），返回错误状态")
                return {
                    "error": f"{func_name} 执行超时（{seconds}秒）",
                    "messages": [{"role": func_name, "content": f"执行超时（{seconds}秒）"}],
                }

        return wrapper

    return decorator
