"""Lightweight trace builder for execution traces."""

from __future__ import annotations

import time
from typing import Any


def make_trace(
    *,
    phase: str,
    status: str = "completed",
    title: str,
    detail: str = "",
    tool_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a single trace entry dict."""
    return {
        "phase": phase,
        "status": status,
        "title": title,
        "detail": detail,
        "tool_name": tool_name,
        "metadata": metadata or {},
    }


class TracedCall:
    """Context manager for timing and tracing a tool / DB call.

    Usage::

        with TracedCall(phase="tool_call", tool_name="get_flood_situation_overview",
                        title="获取全局水情概览") as tc:
            overview = await db.get_flood_situation_overview()
            tc.complete(output_summary=f"{len(overview['stations'])} 个站点")
        traces.append(tc.trace)
    """

    def __init__(
        self,
        *,
        phase: str,
        tool_name: str,
        title: str,
        input_summary: str = "",
    ) -> None:
        self.trace: dict[str, Any] = {
            "phase": phase,
            "tool_name": tool_name,
            "title": title,
            "status": "started",
            "detail": "",
            "metadata": {"input_summary": input_summary},
        }
        self._start: float = 0

    def __enter__(self) -> TracedCall:
        self._start = time.monotonic()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        duration_ms = int((time.monotonic() - self._start) * 1000)
        self.trace["metadata"]["duration_ms"] = duration_ms
        if exc_type is not None:
            self.trace["status"] = "failed"
            self.trace["detail"] = str(exc_val)[:200]
        return False  # never suppress exceptions

    def complete(self, *, output_summary: str = "", detail: str = "") -> dict[str, Any]:
        """Mark the call as completed and attach result summaries."""
        self.trace["status"] = "completed"
        if output_summary:
            self.trace["metadata"]["output_summary"] = output_summary
        if detail:
            self.trace["detail"] = detail
        return self.trace
