"""Very small tool abstraction used in tests and deterministic agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass
class SimpleTool:
    name: str
    _func: Callable

    def invoke(self, payload: dict) -> str:
        return self._func(payload)

    async def ainvoke(self, payload: dict) -> str:
        result = self._func(payload)
        if hasattr(result, "__await__"):
            return await result
        return result
