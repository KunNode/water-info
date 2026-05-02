"""LangGraph memory loader and writer nodes."""

from __future__ import annotations

import logging

from app.memory import get_memory_service

logger = logging.getLogger(__name__)

_TURN_RESET = {
    "iteration": 0,
    "next_agent": "",
    "intent": "",
    "supervisor_reasoning": "",
    "focus_station_query": "",
    "focus_station": {},
    "answer_policy": {},
    "data_summary": "",
    "overview_data": {},
    "weather_forecast": {},
    "risk_assessment": None,
    "emergency_plan": None,
    "resource_plan": [],
    "notifications": [],
    "evidence": [],
    "evidence_context": [],
    "rag_target": "",
    "rag_call_count": 0,
    "rag_query_cache": {},
    "rag_skip_reasons": [],
    "final_response": "",
    "final_response_draft": "",
    "error": "",
}


def _runtime_store(runtime) -> object | None:
    return getattr(runtime, "store", None) if runtime is not None else None


def _recent_session_messages(state: dict, *, limit: int = 10) -> list[dict[str, str]]:
    messages = []
    for item in state.get("messages") or []:
        role = item.get("role") if isinstance(item, dict) else getattr(item, "role", "")
        content = item.get("content") if isinstance(item, dict) else getattr(item, "content", "")
        if role not in {"user", "assistant"} or not content:
            continue
        messages.append({"role": str(role), "content": str(content)[:1000]})
    return messages[-limit:]


async def memory_loader_node(state: dict, runtime=None) -> dict:
    session_id = str(state.get("session_id") or "")
    query = str(state.get("user_query") or "")
    if not session_id:
        return {"memory_context": {}}
    try:
        context = await get_memory_service().load_context(
            user_id=str(state.get("user_id") or ""),
            session_id=session_id,
            query=query,
            recent_messages=_recent_session_messages(state),
            store=_runtime_store(runtime),
        )
        return {
            **_TURN_RESET,
            "current_agent": "memory_loader",
            "memory_context": context.to_prompt_context(),
        }
    except Exception as exc:
        logger.debug("[%s] memory loader skipped: %s", session_id, exc)
        return {"memory_context": {}}


async def memory_writer_node(state: dict, runtime=None) -> dict:
    session_id = str(state.get("session_id") or "")
    try:
        result = await get_memory_service().write_from_state(state, store=_runtime_store(runtime))
    except Exception as exc:
        logger.debug("[%s] memory writer skipped: %s", session_id, exc)
        result = {"saved": 0, "error": str(exc)}
    return {
        "current_agent": "memory_writer",
        "memory_write_result": result,
    }
