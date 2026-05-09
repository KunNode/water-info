"""Verify that conversation_assistant and knowledge_retriever write drafts only.

These nodes used to terminate the workflow by writing `final_response` directly,
but they now hand off via `final_response_draft` so the unified final_response_node
can run its consistency validation and evidence dedup over every workflow path.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from app.agents.conversation_assistant import conversation_assistant_node
from app.agents.knowledge_retriever import knowledge_retriever_node


@pytest.mark.asyncio
async def test_conversation_assistant_writes_only_draft():
    with patch(
        "app.agents.conversation_assistant.get_llm",
        return_value=SimpleNamespace(is_enabled=False),
    ):
        result = await conversation_assistant_node({"user_query": "你好"})

    assert "final_response" not in result
    assert "final_response_draft" in result
    assert "防汛 AI 助手" in result["final_response_draft"]


@pytest.mark.asyncio
async def test_conversation_assistant_uses_recent_session_memory_without_llm():
    with patch(
        "app.agents.conversation_assistant.get_llm",
        return_value=SimpleNamespace(is_enabled=False),
    ):
        result = await conversation_assistant_node({
            "user_query": "刚才这轮会话里我的临时口令是什么？",
            "memory_context": {
                "recent_session_messages": [
                    {"role": "user", "content": "这轮会话里，我的临时口令是蓝色水位线。"},
                    {"role": "assistant", "content": "好的。"},
                ]
            },
        })

    assert "蓝色水位线" in result["final_response_draft"]


@pytest.mark.asyncio
async def test_conversation_assistant_uses_same_session_assistant_alias_before_llm():
    llm = SimpleNamespace(
        is_enabled=True,
        ainvoke=AsyncMock(return_value=SimpleNamespace(content="你好！我是防汛智能助手。")),
    )

    with patch("app.agents.conversation_assistant.get_llm", return_value=llm):
        result = await conversation_assistant_node({
            "user_query": "你是谁",
            "memory_context": {
                "recent_session_messages": [
                    {"role": "user", "content": "你现在叫江西水利电力大学水宝宝"},
                    {"role": "assistant", "content": "好的，收到！"},
                    {"role": "user", "content": "你是谁"},
                ]
            },
        })

    assert "江西水利电力大学水宝宝" in result["final_response_draft"]
    llm.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_conversation_assistant_does_not_use_long_term_memory_for_identity_alias():
    llm = SimpleNamespace(
        is_enabled=True,
        ainvoke=AsyncMock(return_value=SimpleNamespace(content="我是江西水利电力大学水宝宝。")),
    )

    with patch("app.agents.conversation_assistant.get_llm", return_value=llm):
        result = await conversation_assistant_node({
            "user_query": "你是谁",
            "memory_context": {
                "recent_session_messages": [],
                "long_term_memories": [
                    {
                        "type": "fact",
                        "content": "用户曾在其他会话要求助手叫江西水利电力大学水宝宝。",
                    }
                ],
            },
        })

    assert "江西水利电力大学水宝宝" not in result["final_response_draft"]
    llm.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_knowledge_retriever_answer_mode_writes_draft():
    with patch(
        "app.agents.knowledge_retriever.search_knowledge_base", return_value=[]
    ), patch(
        "app.agents.knowledge_retriever.get_llm",
        return_value=SimpleNamespace(is_enabled=False),
    ):
        result = await knowledge_retriever_node(
            {"user_query": "防汛预案管理办法是什么", "rag_target": "answer"}
        )

    assert "final_response" not in result
    assert "final_response_draft" in result


@pytest.mark.asyncio
async def test_knowledge_retriever_preflight_mode_does_not_set_draft():
    with patch(
        "app.agents.knowledge_retriever.search_knowledge_base", return_value=[]
    ):
        result = await knowledge_retriever_node(
            {"user_query": "为预案准备依据", "rag_target": "preflight_plan"}
        )

    assert "final_response" not in result
    assert "final_response_draft" not in result
