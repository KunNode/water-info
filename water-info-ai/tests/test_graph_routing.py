"""测试图路由函数"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.graph import _route_from_memory_loader, _route_from_supervisor
from app.memory.service import MemoryLoadError


class TestRouteFromSupervisor:
    """测试 _route_from_supervisor 函数"""

    def test_end_routes_to_final_response(self):
        state = {"next_agent": "__end__"}
        assert _route_from_supervisor(state) == "final_response"

    def test_data_analyst_route(self):
        state = {"next_agent": "data_analyst"}
        assert _route_from_supervisor(state) == "data_analyst"

    def test_risk_assessor_route(self):
        state = {"next_agent": "risk_assessor"}
        assert _route_from_supervisor(state) == "risk_assessor"

    def test_plan_generator_route(self):
        state = {"next_agent": "plan_generator"}
        assert _route_from_supervisor(state) == "plan_generator"

    def test_resource_dispatcher_route(self):
        state = {"next_agent": "resource_dispatcher"}
        assert _route_from_supervisor(state) == "resource_dispatcher"

    def test_notification_route(self):
        state = {"next_agent": "notification"}
        assert _route_from_supervisor(state) == "notification"

    def test_execution_monitor_route(self):
        state = {"next_agent": "execution_monitor"}
        assert _route_from_supervisor(state) == "execution_monitor"

    def test_parallel_dispatch_route(self):
        state = {"next_agent": "parallel_dispatch"}
        assert _route_from_supervisor(state) == "parallel_dispatch"

    def test_knowledge_retriever_route(self):
        state = {"next_agent": "knowledge_retriever"}
        assert _route_from_supervisor(state) == "knowledge_retriever"

    def test_missing_next_agent_defaults_to_final_response(self):
        state = {}
        assert _route_from_supervisor(state) == "final_response"


class TestRouteFromMemoryLoader:
    """Unit tests for ``_route_from_memory_loader``.

    The route function is the single guard that stops the graph from running
    ``supervisor → final_response → memory_writer`` after an unrecoverable
    memory-load failure (Req 4.4).
    """

    def test_empty_state_routes_to_supervisor(self):
        assert _route_from_memory_loader({}) == "supervisor"

    def test_normal_state_routes_to_supervisor(self):
        state = {"memory_context": {"recent_session_messages": []}, "current_agent": "memory_loader"}
        assert _route_from_memory_loader(state) == "supervisor"

    def test_memory_load_failed_error_routes_to_end(self):
        state = {"error": "memory_load_failed: conversation_messages", "next_agent": "__end__"}
        assert _route_from_memory_loader(state) == "__end__"

    def test_memory_load_failed_different_source_routes_to_end(self):
        state = {"error": "memory_load_failed: snapshot", "next_agent": "__end__"}
        assert _route_from_memory_loader(state) == "__end__"

    def test_next_agent_end_alone_routes_to_end(self):
        # Defence-in-depth: even if the error string was stripped somewhere upstream,
        # next_agent="__end__" still short-circuits the graph.
        state = {"next_agent": "__end__"}
        assert _route_from_memory_loader(state) == "__end__"

    def test_unrelated_error_does_not_short_circuit(self):
        # Non-memory errors (e.g. downstream agent failures) must not hijack this edge.
        state = {"error": "plan_generation_failed: llm timeout"}
        assert _route_from_memory_loader(state) == "supervisor"


@pytest.mark.asyncio
async def test_memory_loader_routes_to_end_on_memory_load_failed(monkeypatch):
    """End-to-end: when ``load_context`` raises ``MemoryLoadError``, the compiled
    graph must short-circuit before reaching ``supervisor`` or ``final_response``.

    Without the conditional edge (bug), LangGraph would ignore the
    ``next_agent="__end__"`` signal set by ``memory_loader_node`` because the
    edge was an unconditional ``add_edge("memory_loader", "supervisor")``. The
    graph would then fabricate a "处理完成" reply via ``final_response`` and
    persist it, even though the user's conversation history could not be
    loaded.
    """

    # Stub the memory service so the real ``memory_loader_node`` raises
    # ``MemoryLoadError`` and falls into the Req 4.4 short-circuit branch.
    failing_service = AsyncMock()
    failing_service.load_context = AsyncMock(
        side_effect=MemoryLoadError("conversation_messages")
    )

    supervisor_spy = AsyncMock(return_value={"next_agent": "final_response"})
    final_response_spy = AsyncMock(return_value={"final_response": "should not happen"})

    # Patch the symbols at their usage sites. ``memory_loader_node`` calls
    # ``get_memory_service`` via ``app.memory`` (re-exported from
    # ``app.agents.memory``); ``supervisor_node`` / ``final_response_node`` are
    # bound into ``app.graph`` at import time and captured by ``audited_agent``
    # closures — patching before ``build_flood_response_graph()`` is required.
    monkeypatch.setattr("app.agents.memory.get_memory_service", lambda: failing_service)
    monkeypatch.setattr("app.graph.supervisor_node", supervisor_spy)
    monkeypatch.setattr("app.graph.final_response_node", final_response_spy)

    # Also disable the audit recorder so ``audited_agent`` stays on the
    # lightweight code path without touching DB-backed recorders.
    from app.graph import build_flood_response_graph as _build

    fresh_graph = _build()

    initial_state = {
        "session_id": "test-routing",
        "user_id": "u-routing",
        "user_query": "继续上一轮的研判",
        "messages": [],
        "iteration": 0,
    }
    final_state = await fresh_graph.ainvoke(
        initial_state,
        {"configurable": {"thread_id": "test-routing"}},
    )

    # Req 4.4: the error signal survives to the caller so the SSE / non-stream
    # endpoints can translate it into a structured response.
    assert str(final_state.get("error") or "").startswith("memory_load_failed:")
    assert final_state.get("next_agent") == "__end__"

    # The graph must terminate at memory_loader — neither supervisor nor
    # final_response should have been invoked. Before the fix these would have
    # been awaited because of the unconditional edge.
    supervisor_spy.assert_not_awaited()
    final_response_spy.assert_not_awaited()
    failing_service.load_context.assert_awaited_once()
