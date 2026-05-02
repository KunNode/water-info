"""Memory service tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.memory.service import MemoryService, build_memory_namespaces, build_write_namespace


@pytest.mark.asyncio
async def test_load_context_returns_summary_snapshot_and_memories():
    db = SimpleNamespace(
        get_latest_conversation_summary=AsyncMock(return_value={"summary": "上一轮讨论了翠屏湖水位。"}),
        get_conversation_snapshot=AsyncMock(return_value={"risk_level": "moderate"}),
        search_memory_items=AsyncMock(return_value=[
            {
                "id": 1,
                "namespace": "user:u-1:flood_assistant",
                "item_type": "preference",
                "content": "用户偏好先看翠屏湖站点。",
                "importance": 0.8,
                "confidence": 0.9,
                "metadata": {},
                "source_session_id": "s-0",
                "updated_at": "2026-05-02",
                "score": 0.7,
            }
        ]),
    )
    embedder = SimpleNamespace(is_enabled=False)

    with (
        patch("app.memory.service.get_db_service", return_value=db),
        patch("app.memory.service.get_embedding_client", return_value=embedder),
    ):
        context = await MemoryService().load_context(
            user_id="u-1",
            session_id="s-1",
            query="翠屏湖情况",
            recent_messages=[{"role": "user", "content": "上一轮我说关注翠屏湖"}],
        )

    prompt_context = context.to_prompt_context()
    assert prompt_context["conversation_summary"] == "上一轮讨论了翠屏湖水位。"
    assert prompt_context["recent_session_messages"] == [{"role": "user", "content": "上一轮我说关注翠屏湖"}]
    assert prompt_context["business_snapshot"]["risk_level"] == "moderate"
    assert prompt_context["long_term_memories"][0]["content"] == "用户偏好先看翠屏湖站点。"
    db.search_memory_items.assert_awaited_once()


@pytest.mark.asyncio
async def test_write_from_state_saves_explicit_memory_without_llm_or_embeddings():
    db = SimpleNamespace(
        upsert_memory_item=AsyncMock(return_value=3),
        get_conversation_messages=AsyncMock(return_value=[]),
    )
    embedder = SimpleNamespace(is_enabled=False)
    llm = SimpleNamespace(is_enabled=False)

    with (
        patch("app.memory.service.get_db_service", return_value=db),
        patch("app.memory.service.get_embedding_client", return_value=embedder),
        patch("app.memory.service.get_llm", return_value=llm),
    ):
        result = await MemoryService().write_from_state({
            "session_id": "s-1",
            "user_id": "u-1",
            "user_query": "请记住 我的指挥偏好是先看翠屏湖站点",
        })

    assert result["saved"] == 1
    kwargs = db.upsert_memory_item.await_args.kwargs
    assert kwargs["namespace"] == "user:u-1:flood_assistant"
    assert kwargs["item_type"] == "preference"
    assert kwargs["content"] == "我的指挥偏好是先看翠屏湖站点"


@pytest.mark.asyncio
async def test_explicit_memory_request_skips_llm_extraction_to_avoid_duplicates():
    llm = SimpleNamespace(is_enabled=True, ainvoke=AsyncMock())

    with patch("app.memory.service.get_llm", return_value=llm):
        candidates = await MemoryService().extract_candidates({
            "session_id": "s-1",
            "user_query": "请记住 我的指挥偏好是先看翠屏湖站点",
        })

    assert len(candidates) == 1
    assert candidates[0].item_type.value == "preference"
    llm.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_temporary_session_context_is_not_written_to_long_term_memory():
    llm = SimpleNamespace(is_enabled=True, ainvoke=AsyncMock())

    with patch("app.memory.service.get_llm", return_value=llm):
        candidates = await MemoryService().extract_candidates({
            "session_id": "s-1",
            "user_query": "这轮会话里，我的临时口令是绿色堤岸。只在当前会话里接上。",
        })

    assert candidates == []
    llm.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_write_from_state_mirrors_saved_memory_to_langgraph_store():
    db = SimpleNamespace(
        upsert_memory_item=AsyncMock(return_value=42),
        get_conversation_messages=AsyncMock(return_value=[]),
    )
    store = SimpleNamespace(aput=AsyncMock())
    embedder = SimpleNamespace(is_enabled=False)
    llm = SimpleNamespace(is_enabled=False)

    with (
        patch("app.memory.service.get_db_service", return_value=db),
        patch("app.memory.service.get_embedding_client", return_value=embedder),
        patch("app.memory.service.get_llm", return_value=llm),
    ):
        result = await MemoryService().write_from_state(
            {
                "session_id": "s-1",
                "user_id": "u-1",
                "user_query": "请记住 我的指挥偏好是先看北闸站",
            },
            store=store,
        )

    assert result["store_saved"] is True
    store.aput.assert_awaited_once()
    namespace, key, value = store.aput.await_args.args
    assert namespace == ("user", "u-1", "flood_assistant")
    assert key == "42"
    assert value["content"] == "我的指挥偏好是先看北闸站"


def test_memory_namespace_helpers_avoid_cross_user_anonymous_leakage():
    assert build_memory_namespaces("u-1", "s-1")[0] == "user:u-1:flood_assistant"
    assert build_memory_namespaces("", "s-1")[0] == "anonymous_session:s-1:flood_assistant"
    assert build_write_namespace("", "s-1") == "anonymous_session:s-1:flood_assistant"
