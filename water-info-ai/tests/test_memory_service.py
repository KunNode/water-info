"""Memory service tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.memory.service import (
    CONTEXT_HISTORY_LIMIT,
    MemoryLoadError,
    MemoryService,
    build_memory_namespaces,
    build_write_namespace,
)


@pytest.mark.asyncio
async def test_load_context_returns_summary_snapshot_and_memories():
    db = SimpleNamespace(
        get_latest_conversation_summary=AsyncMock(return_value={"summary": "上一轮讨论了翠屏湖水位。"}),
        get_conversation_snapshot=AsyncMock(return_value={"risk_level": "moderate"}),
        get_conversation_messages=AsyncMock(return_value=[
            {"id": 1, "role": "user", "content": "上一轮我说关注翠屏湖", "status": "completed"},
        ]),
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
    db.get_conversation_messages.assert_awaited_once_with("s-1", limit=20)
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


# ── Task 1.2: MemoryLoadError propagation + always-read-DB semantics ──────────


@pytest.mark.asyncio
async def test_load_context_raises_memory_load_error_when_summary_read_fails():
    db = SimpleNamespace(
        get_latest_conversation_summary=AsyncMock(side_effect=RuntimeError("boom")),
        get_conversation_snapshot=AsyncMock(return_value=None),
        get_conversation_messages=AsyncMock(return_value=[]),
        search_memory_items=AsyncMock(return_value=[]),
    )
    embedder = SimpleNamespace(is_enabled=False)

    with (
        patch("app.memory.service.get_db_service", return_value=db),
        patch("app.memory.service.get_embedding_client", return_value=embedder),
    ):
        with pytest.raises(MemoryLoadError) as excinfo:
            await MemoryService().load_context(session_id="s-1", query="hi")

    assert excinfo.value.source == "summary"
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    # Critical read failed → downstream reads must NOT execute.
    db.get_conversation_snapshot.assert_not_awaited()
    db.get_conversation_messages.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_context_raises_memory_load_error_when_snapshot_read_fails():
    db = SimpleNamespace(
        get_latest_conversation_summary=AsyncMock(return_value={"summary": "ok"}),
        get_conversation_snapshot=AsyncMock(side_effect=RuntimeError("snap boom")),
        get_conversation_messages=AsyncMock(return_value=[]),
        search_memory_items=AsyncMock(return_value=[]),
    )
    embedder = SimpleNamespace(is_enabled=False)

    with (
        patch("app.memory.service.get_db_service", return_value=db),
        patch("app.memory.service.get_embedding_client", return_value=embedder),
    ):
        with pytest.raises(MemoryLoadError) as excinfo:
            await MemoryService().load_context(session_id="s-1", query="hi")

    assert excinfo.value.source == "snapshot"
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    db.get_conversation_messages.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_context_raises_memory_load_error_when_messages_read_fails():
    db = SimpleNamespace(
        get_latest_conversation_summary=AsyncMock(return_value={"summary": "ok"}),
        get_conversation_snapshot=AsyncMock(return_value=None),
        get_conversation_messages=AsyncMock(side_effect=RuntimeError("msg boom")),
        search_memory_items=AsyncMock(return_value=[]),
    )
    embedder = SimpleNamespace(is_enabled=False)

    with (
        patch("app.memory.service.get_db_service", return_value=db),
        patch("app.memory.service.get_embedding_client", return_value=embedder),
    ):
        with pytest.raises(MemoryLoadError) as excinfo:
            await MemoryService().load_context(
                session_id="s-1",
                query="hi",
                recent_messages=[{"role": "user", "content": "preloaded"}],
            )

    assert excinfo.value.source == "conversation_messages"
    assert isinstance(excinfo.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_load_context_always_reads_db_even_when_preloaded_history_provided():
    """Req 3.2: recent_messages from callers must not suppress the DB read."""
    db_rows = [
        {"id": 2, "role": "assistant", "content": "db reply", "status": "completed"},
        {"id": 1, "role": "user", "content": "db query", "status": "completed"},
    ]
    db = SimpleNamespace(
        get_latest_conversation_summary=AsyncMock(return_value=None),
        get_conversation_snapshot=AsyncMock(return_value=None),
        get_conversation_messages=AsyncMock(return_value=db_rows),
        search_memory_items=AsyncMock(return_value=[]),
    )
    embedder = SimpleNamespace(is_enabled=False)

    with (
        patch("app.memory.service.get_db_service", return_value=db),
        patch("app.memory.service.get_embedding_client", return_value=embedder),
    ):
        context = await MemoryService().load_context(
            session_id="s-1",
            query="hi",
            recent_messages=[{"role": "user", "content": "stale preload"}],
        )

    db.get_conversation_messages.assert_awaited_once_with("s-1", limit=CONTEXT_HISTORY_LIMIT)
    # DB result wins over pre-populated history, and must be sorted by id asc.
    assert context.recent_messages == [
        {"role": "user", "content": "db query"},
        {"role": "assistant", "content": "db reply"},
    ]


@pytest.mark.asyncio
async def test_load_context_falls_back_to_caller_messages_when_db_empty():
    """If the DB returns no usable rows, keep the caller-provided pre-load."""
    db = SimpleNamespace(
        get_latest_conversation_summary=AsyncMock(return_value=None),
        get_conversation_snapshot=AsyncMock(return_value=None),
        get_conversation_messages=AsyncMock(return_value=[]),
        search_memory_items=AsyncMock(return_value=[]),
    )
    embedder = SimpleNamespace(is_enabled=False)

    with (
        patch("app.memory.service.get_db_service", return_value=db),
        patch("app.memory.service.get_embedding_client", return_value=embedder),
    ):
        context = await MemoryService().load_context(
            session_id="s-new",
            query="hi",
            recent_messages=[{"role": "user", "content": "first question"}],
        )

    assert context.recent_messages == [{"role": "user", "content": "first question"}]


@pytest.mark.asyncio
async def test_load_context_swallows_memory_items_search_failure():
    """search_memory_items is non-critical and must degrade silently."""
    db = SimpleNamespace(
        get_latest_conversation_summary=AsyncMock(return_value=None),
        get_conversation_snapshot=AsyncMock(return_value=None),
        get_conversation_messages=AsyncMock(return_value=[]),
        search_memory_items=AsyncMock(side_effect=RuntimeError("search boom")),
    )
    embedder = SimpleNamespace(is_enabled=False)

    with (
        patch("app.memory.service.get_db_service", return_value=db),
        patch("app.memory.service.get_embedding_client", return_value=embedder),
    ):
        # Must not raise — memory_items is not part of the critical path.
        context = await MemoryService().load_context(session_id="s-1", query="hi")

    assert context.memories == []


# ── Task 1.3: Property 3 — MemoryService.load_context completeness ────────────
#
# Feature: ai-session-history-resume, Property 3: load_context completeness
# Validates: Requirements 3.2, 3.3
#
# Hypothesis generates 0 ≤ N ≤ CONTEXT_HISTORY_LIMIT `conversation_messages`
# rows (mixing valid + invalid role/status/content to exercise the filter),
# plus optional `conversation_snapshots` and `conversation_summary` rows, and
# drives `MemoryService.load_context` through an in-memory fake DatabaseService.
#
# Invariants (per task 1.3 and design.md §Correctness Properties):
#   • len(result.recent_messages) equals the count of rows whose role ∈
#     {user, assistant}, content.strip() ≠ "", and status ∉ {streaming, failed}
#   • result.recent_messages is sorted ascending by DB `id` regardless of the
#     order the fake DB returns rows in
#   • result.snapshot["session_id"] == input session_id when a snapshot row
#     exists; result.snapshot is None otherwise
#   • result.summary == latest_summary_row["summary"] when the summary row
#     exists; "" otherwise
import asyncio

from hypothesis import given, settings
from hypothesis import strategies as st


@st.composite
def _load_context_scenario(draw):
    """Generate (session_id, rows, snapshot_row, summary_row)."""
    session_id = draw(st.from_regex(r"[a-z0-9\-]{4,20}", fullmatch=True))

    # Mixed-validity rows (role / content / status) so the filter is exercised.
    rows = draw(
        st.lists(
            st.fixed_dictionaries(
                {
                    "id": st.integers(min_value=1, max_value=100_000),
                    "role": st.sampled_from(["user", "assistant", "system", "tool", ""]),
                    "content": st.one_of(
                        st.just(""),
                        st.text(alphabet=" \t\n", min_size=1, max_size=5),  # whitespace-only
                        st.text(min_size=1, max_size=80),
                    ),
                    "status": st.sampled_from(["completed", "streaming", "failed"]),
                }
            ),
            max_size=CONTEXT_HISTORY_LIMIT,
            unique_by=lambda row: row["id"],
        )
    )

    snapshot_row = draw(
        st.one_of(
            st.none(),
            st.fixed_dictionaries(
                {
                    "session_id": st.just(session_id),
                    "risk_level": st.sampled_from(["none", "low", "moderate", "high", "critical"]),
                    "plan_info": st.just({}),
                    "agent_status_summary": st.just({}),
                    "query_count": st.integers(min_value=0, max_value=100),
                    "updated_at": st.none(),
                }
            ),
        )
    )

    summary_row = draw(
        st.one_of(
            st.none(),
            st.fixed_dictionaries({"summary": st.text(max_size=300)}),
        )
    )

    # Permute row order so we can verify `load_context` sorts by `id` ascending
    # even when the DB returns them in a different order.
    permuted = draw(st.permutations(rows))
    return session_id, list(permuted), snapshot_row, summary_row


@given(scenario=_load_context_scenario())
@settings(max_examples=100, deadline=None)
def test_load_context_completeness_property(scenario):
    """Feature: ai-session-history-resume, Property 3: load_context completeness

    Validates: Requirements 3.2, 3.3
    """
    session_id, rows, snapshot_row, summary_row = scenario

    async def _run():
        db = SimpleNamespace(
            get_latest_conversation_summary=AsyncMock(return_value=summary_row),
            get_conversation_snapshot=AsyncMock(return_value=snapshot_row),
            get_conversation_messages=AsyncMock(return_value=list(rows)),
            search_memory_items=AsyncMock(return_value=[]),
        )
        embedder = SimpleNamespace(is_enabled=False)
        with (
            patch("app.memory.service.get_db_service", return_value=db),
            patch("app.memory.service.get_embedding_client", return_value=embedder),
        ):
            return await MemoryService().load_context(session_id=session_id, query="test")

    context = asyncio.run(_run())

    # Reference implementation of the same filter used by _normalize_chat_messages.
    expected_valid = [
        row
        for row in rows
        if row["role"] in {"user", "assistant"}
        and str(row.get("content") or "").strip()
        and str(row.get("status") or "completed") not in {"streaming", "failed"}
    ]
    expected_sorted = sorted(expected_valid, key=lambda row: int(row["id"]))

    # Invariant 1: length matches the filtered DB count.
    assert len(context.recent_messages) == len(expected_sorted), (
        f"expected {len(expected_sorted)} recent messages, got {len(context.recent_messages)}"
    )

    # Invariant 2: ascending order by DB id (independent of how rows were fed in).
    for got, row in zip(context.recent_messages, expected_sorted):
        assert got["role"] == row["role"]
        # Service strips & truncates content to 1000 chars.
        assert got["content"] == str(row["content"]).strip()[:1000]
    assert all(msg["role"] in {"user", "assistant"} for msg in context.recent_messages)
    assert all(msg["content"] != "" for msg in context.recent_messages)

    # Invariant 3: snapshot round-trip.
    if snapshot_row is None:
        assert context.snapshot is None
    else:
        assert context.snapshot is not None
        assert context.snapshot["session_id"] == session_id

    # Invariant 4: summary equals latest row's `summary` field, else "".
    if summary_row is None:
        assert context.summary == ""
    else:
        assert context.summary == str(summary_row.get("summary") or "")
