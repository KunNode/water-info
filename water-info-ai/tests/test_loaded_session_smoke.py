"""Loaded-Session smoke test (Task 3.4).

Feature: ai-session-history-resume
Validates: Requirements 3.5

End-to-end smoke test for the `/api/v1/flood/query/stream` endpoint when the
caller resumes an existing session. The test seeds the DB mock with a short
conversation history that mentions domain entities (`翠屏湖`, `风险等级: high`),
then streams a follow-up request on the same ``session_id``. The real
LangGraph workflow is executed, but the LLM client is replaced with a
deterministic mock that:

* For routing-style JSON prompts (supervisor): returns a minimal routing
  decision so the graph stays on the cheap ``conversation_assistant →
  final_response`` path.
* For the ``conversation_assistant`` prompt: parses the JSON payload,
  extracts ``memory_context.recent_session_messages`` contents, and weaves
  them into the reply.

Because Task 2.2 requires every LLM-invoking agent to embed
``memory_context`` via ``session_context_payload(state)`` at the top level
of its prompt, this test also acts as a cross-check: the historical
entities only show up in ``final_response`` iff the prompt injection chain
is intact (memory_loader → state['memory_context'] → agent prompt →
mocked LLM echo).

Only 1-2 cases — this is an integration smoke test, not a property test.
"""

from __future__ import annotations

import json
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.smoke


# ── DB mock with pre-seeded history ───────────────────────────────────────────


def _build_seeded_db_mock(history_rows: list[dict]):
    """Database stub where ``get_conversation_messages`` returns pre-seeded rows.

    The rows follow the same shape produced by
    :meth:`DatabaseService.get_conversation_messages`:
    ``{id, role, content, message_type, status, metadata, created_at}``.
    ``id`` ascending — matches the ORDER BY in the real query.
    """
    return SimpleNamespace(
        _get_pool=AsyncMock(return_value=object()),
        ensure_plan_tables=AsyncMock(),
        ensure_conversation_tables=AsyncMock(),
        ensure_kb_tables=AsyncMock(),
        close=AsyncMock(),
        ensure_or_create_session=AsyncMock(),
        save_conversation_message=AsyncMock(side_effect=[501, 502, 503, 504]),
        update_message_content=AsyncMock(),
        # Memory loader + _load_session_history both go through this.
        get_conversation_messages=AsyncMock(return_value=history_rows),
        get_latest_conversation_summary=AsyncMock(return_value=None),
        get_conversation_snapshot=AsyncMock(return_value=None),
        save_conversation_snapshot=AsyncMock(),
        save_emergency_plan=AsyncMock(),
        save_resource_allocations=AsyncMock(),
        save_notifications=AsyncMock(),
        list_memory_items=AsyncMock(return_value=[]),
        update_memory_item=AsyncMock(return_value=None),
        delete_memory_item=AsyncMock(return_value=True),
        # Memory writer path: never reached (query triggers memory extraction
        # that returns no candidates), but guard against accidental calls.
        search_memory_items=AsyncMock(return_value=[]),
        upsert_memory_item=AsyncMock(return_value=1),
        save_conversation_summary=AsyncMock(),
    )


def _build_session_mock():
    """Redis short-term session stub — empty history forces DB fallback."""
    return SimpleNamespace(
        get_history=AsyncMock(return_value=[]),
        save_turn=AsyncMock(),
        close=AsyncMock(),
    )


# ── LLM mock that echoes memory_context entities ─────────────────────────────


def _build_smart_llm_mock():
    """Mock LLM that echoes ``memory_context.recent_session_messages`` content.

    The LLM layer in the real service (see ``app.services.llm.OpenAICompatibleLLM``)
    is called by each LLM-invoking agent with either:

    - a JSON-encoded payload (every agent in this spec's scope), OR
    - a plain-string message (legacy paths).

    When the caller asks for ``response_format={"type": "json_object"}`` the
    mock returns either a routing decision (supervisor shape) or an empty
    ``{}`` (plan/final-response shape, which then triggers each agent's
    deterministic fallback — we don't want the LLM to fabricate structured
    plan content in the smoke path).

    For natural-language prompts (conversation_assistant), the mock parses
    the JSON prompt, pulls every ``recent_session_messages[*].content``
    string, and returns a reply that quotes them. This deterministically
    surfaces historical entities inside ``final_response`` without any real
    LLM call.
    """

    async def _ainvoke(prompt, *, system_prompt=None, temperature=0.2, response_format=None, **_):
        payload = _safe_load_json(prompt)

        # Routing-style JSON prompt (supervisor / structured-output harnesses).
        if response_format and response_format.get("type") == "json_object":
            if "workflow_state" in payload:
                # Supervisor — force conversation_assistant so we stay on the
                # lightweight chat path and exercise the memory-injection chain.
                return SimpleNamespace(
                    content=json.dumps(
                        {
                            "next_agent": "conversation_assistant",
                            "intent": "general_chat",
                            "reasoning": "smoke: route to conversation_assistant",
                        },
                        ensure_ascii=False,
                    )
                )
            # Any other structured-output caller (plan_generator harness,
            # final_response repair, etc.). Returning ``{}`` fails the schema
            # so each caller falls back to its deterministic path — which is
            # what we want for a minimal smoke.
            return SimpleNamespace(content="{}")

        # Natural-language prompt — the conversation_assistant path. Echo the
        # historical entities so the assertion below can observe them.
        memory_context = payload.get("memory_context") or {}
        recent = memory_context.get("recent_session_messages") or []
        quoted: list[str] = []
        for item in recent:
            if not isinstance(item, dict):
                continue
            text = str(item.get("content") or "").strip()
            if text:
                quoted.append(text)

        body = " ".join(quoted) if quoted else ""
        reply = f"继续之前关于该话题的分析。历史上下文：{body}".strip()
        return SimpleNamespace(content=reply)

    return SimpleNamespace(
        is_enabled=True,
        ainvoke=AsyncMock(side_effect=_ainvoke),
        aclose=AsyncMock(),
    )


def _safe_load_json(prompt) -> dict:
    """Best-effort JSON decoding — returns ``{}`` for non-JSON prompts."""
    if not isinstance(prompt, str):
        return {}
    try:
        loaded = json.loads(prompt)
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


# ── Patched client plumbing ───────────────────────────────────────────────────


# Every module that imports ``get_llm`` / ``get_db_service`` directly (the
# pattern is ``from X import get_Y``) needs a separate patch target — the
# Python name binding is per-module. Only modules reached by this smoke
# path are patched here; adding more would bloat the mock surface without
# changing behavior.
_LLM_PATCH_TARGETS = (
    "app.agents.supervisor.get_llm",
    "app.agents.conversation_assistant.get_llm",
    "app.agents.final_response.get_llm",
    "app.memory.service.get_llm",
)

_DB_PATCH_TARGETS = (
    "app.main.get_db_service",
    "app.memory.service.get_db_service",
)


@contextmanager
def _patched_smoke_client(*, db_mock, llm_mock, session_mock=None):
    session_mock = session_mock or _build_session_mock()
    with ExitStack() as stack:
        for target in _DB_PATCH_TARGETS:
            stack.enter_context(patch(target, return_value=db_mock))
        for target in _LLM_PATCH_TARGETS:
            stack.enter_context(patch(target, return_value=llm_mock))
        stack.enter_context(
            patch("app.services.session.get_session_service", return_value=session_mock)
        )
        client = stack.enter_context(TestClient(app))
        yield client, db_mock, llm_mock, session_mock


def _drain_stream(client: TestClient, *, session_id: str, query: str) -> str:
    with client.stream(
        "POST",
        "/api/v1/flood/query/stream",
        json={"query": query, "session_id": session_id},
    ) as response:
        assert response.status_code == 200
        return "".join(response.iter_text())


def _extract_final_response_from_stream(body: str) -> str:
    """Return the ``response`` field of the ``final_response`` agent_message event."""
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            event = json.loads(line[len("data: "):])
        except Exception:
            continue
        if (
            event.get("type") == "agent_message"
            and event.get("agent") == "final_response"
            and isinstance(event.get("response"), str)
        ):
            return event["response"]
    raise AssertionError(f"no final_response agent_message found in stream:\n{body}")


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_loaded_session_ai_references_historical_lake_entity():
    """Case 1: seeded history mentions ``翠屏湖`` / ``风险等级: high`` — the AI
    response on the resumed session must reference both historical entities.

    Validates: Requirements 3.5
    """
    session_id = "sess-loaded-entities-001"
    history_rows = [
        {
            "id": 101,
            "role": "user",
            "content": "请评估翠屏湖当前的防汛形势",
            "message_type": "chat",
            "status": "completed",
            "metadata": {},
            "created_at": "2026-05-10T08:00:00+00:00",
        },
        {
            "id": 102,
            "role": "assistant",
            "content": "翠屏湖水位持续上涨，风险等级: high，建议加密巡查并启动响应。",
            "message_type": "chat",
            "status": "completed",
            "metadata": {"version": 1},
            "created_at": "2026-05-10T08:00:05+00:00",
        },
    ]
    db_mock = _build_seeded_db_mock(history_rows)
    llm_mock = _build_smart_llm_mock()

    with _patched_smoke_client(db_mock=db_mock, llm_mock=llm_mock) as (client, _db, _llm, _sess):
        body = _drain_stream(
            client,
            session_id=session_id,
            query="请基于我们之前的沟通继续分析",
        )

    final_text = _extract_final_response_from_stream(body)
    assert "翠屏湖" in final_text, (
        f"final_response must reference the historical lake entity `翠屏湖`, got: {final_text!r}"
    )
    assert "风险等级: high" in final_text, (
        f"final_response must reference the historical risk conclusion `风险等级: high`, "
        f"got: {final_text!r}"
    )

    # The streamed assistant message must ultimately be persisted with the same
    # text (Req 3.6), so the round-trip contract holds between runs.
    db_mock.update_message_content.assert_awaited()
    persisted_call = db_mock.update_message_content.await_args
    assert persisted_call.kwargs.get("status") == "completed"
    assert "翠屏湖" in persisted_call.args[1]
    assert "风险等级: high" in persisted_call.args[1]


def test_loaded_session_ai_references_station_and_risk_from_multiple_turns():
    """Case 2: a longer seeded history with a station code and risk wording
    across multiple turns. The AI response must still surface at least one
    historical entity (``北闸站`` and / or ``风险等级: high``).

    This second case guards against regressions where only the most recent
    message is wired into ``memory_context.recent_session_messages`` (Req 3.2
    says "full recent history, up to the configured limit").

    Validates: Requirements 3.5
    """
    session_id = "sess-loaded-entities-002"
    history_rows = [
        {
            "id": 201,
            "role": "user",
            "content": "我这轮主要关注北闸站",
            "message_type": "chat",
            "status": "completed",
            "metadata": {},
            "created_at": "2026-05-10T09:00:00+00:00",
        },
        {
            "id": 202,
            "role": "assistant",
            "content": "已记录：本会话重点是 北闸站。",
            "message_type": "chat",
            "status": "completed",
            "metadata": {"version": 1},
            "created_at": "2026-05-10T09:00:05+00:00",
        },
        {
            "id": 203,
            "role": "user",
            "content": "刚才的研判结论是什么",
            "message_type": "chat",
            "status": "completed",
            "metadata": {},
            "created_at": "2026-05-10T09:05:00+00:00",
        },
        {
            "id": 204,
            "role": "assistant",
            "content": "北闸站综合研判：风险等级: high，建议持续监测。",
            "message_type": "chat",
            "status": "completed",
            "metadata": {"version": 1},
            "created_at": "2026-05-10T09:05:10+00:00",
        },
    ]
    db_mock = _build_seeded_db_mock(history_rows)
    llm_mock = _build_smart_llm_mock()

    with _patched_smoke_client(db_mock=db_mock, llm_mock=llm_mock) as (client, _db, _llm, _sess):
        body = _drain_stream(
            client,
            session_id=session_id,
            query="请帮我梳理一下后续建议",
        )

    final_text = _extract_final_response_from_stream(body)
    # At minimum both the station and risk entities from earlier turns must
    # surface in the resumed reply — if either is missing, memory_context is
    # being truncated or dropped somewhere in the chain.
    assert "北闸站" in final_text, (
        f"final_response must reference historical station `北闸站`, got: {final_text!r}"
    )
    assert "风险等级: high" in final_text, (
        f"final_response must reference historical risk `风险等级: high`, got: {final_text!r}"
    )
