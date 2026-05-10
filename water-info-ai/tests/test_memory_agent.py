"""Tests for graph memory nodes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.memory import _recent_session_messages, memory_loader_node
from app.memory.models import MemoryContext
from app.memory.service import MemoryLoadError


def test_recent_session_messages_keeps_only_user_and_assistant_messages():
    result = _recent_session_messages({
        "messages": [
            {"role": "system", "content": "internal"},
            {"role": "user", "content": "我的名字是李明"},
            {"role": "conversation_assistant", "content": "internal draft"},
            {"role": "assistant", "content": "好的"},
            {"role": "user", "content": "我叫什么"},
        ]
    })

    assert result == [
        {"role": "user", "content": "我的名字是李明"},
        {"role": "assistant", "content": "好的"},
        {"role": "user", "content": "我叫什么"},
    ]


@pytest.mark.asyncio
async def test_memory_loader_includes_same_session_recent_messages():
    service = SimpleNamespace(
        load_context=AsyncMock(return_value=MemoryContext(recent_messages=[{"role": "user", "content": "我的名字是李明"}]))
    )

    with patch("app.agents.memory.get_memory_service", return_value=service):
        result = await memory_loader_node({
            "session_id": "s-1",
            "user_id": "u-1",
            "user_query": "我叫什么",
            "messages": [
                {"role": "user", "content": "我的名字是李明"},
                {"role": "assistant", "content": "好的"},
                {"role": "user", "content": "我叫什么"},
            ],
        })

    assert result["memory_context"]["recent_session_messages"] == [{"role": "user", "content": "我的名字是李明"}]
    assert result["iteration"] == 0
    assert result["final_response_draft"] == ""
    assert service.load_context.await_args.kwargs["recent_messages"][-1]["content"] == "我叫什么"


@pytest.mark.asyncio
async def test_memory_loader_short_circuits_on_memory_load_error():
    """Req 4.4: when ``load_context`` raises ``MemoryLoadError``, the node must
    set ``error="memory_load_failed: <source>"`` and ``next_agent="__end__"``
    so that ``event_stream`` can map it to a structured SSE error.
    """
    service = SimpleNamespace(
        load_context=AsyncMock(side_effect=MemoryLoadError("conversation_messages"))
    )

    with patch("app.agents.memory.get_memory_service", return_value=service):
        result = await memory_loader_node({
            "session_id": "s-err",
            "user_id": "u-1",
            "user_query": "继续上一轮的研判",
            "messages": [],
        })

    assert result["error"] == "memory_load_failed: conversation_messages"
    assert result["next_agent"] == "__end__"
    assert result["memory_context"] == {}
    assert result["current_agent"] == "memory_loader"
