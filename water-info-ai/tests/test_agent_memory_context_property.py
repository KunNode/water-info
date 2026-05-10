"""Property 4 — every LLM-invoking agent must inject ``memory_context``.

Feature: ai-session-history-resume, Property 4: memory_context ubiquity
Validates: Requirements 3.4

For any non-empty ``memory_context`` (i.e. at least one of
``conversation_summary`` / ``recent_session_messages`` / ``business_snapshot`` /
``long_term_memories`` is non-empty), each LLM-invoking agent node
(``supervisor``, ``conversation_assistant``, ``risk_assessor``,
``plan_generator``, ``final_response``) MUST build its LLM prompt payload so
that the top-level ``memory_context`` key is present and deep-equals
``session_context_payload(state)``.

The invariant is enforced by mocking the shared :func:`app.services.llm.get_llm`
return value so the agent's ``llm.ainvoke`` call is captured. The first
positional argument received by ``ainvoke`` is a JSON-encoded prompt payload;
we decode it and compare ``payload["memory_context"]`` against the canonical
``session_context_payload(state)`` output.

Notes on generator design (smart generators):
- We keep the payload shapes compatible with ``MemoryContext.to_prompt_context``
  so ``session_context_payload`` passes them through unchanged.
- We avoid ``user_query`` substrings that would short-circuit each agent's
  deterministic / fallback branch before the LLM call (e.g. identity questions
  for ``conversation_assistant``, or ``general_chat`` hard-route for
  ``supervisor``).
- We deliberately filter out ``recent_session_messages`` content that would
  match ``conversation_assistant``'s recent-session alias / secret regex so the
  LLM branch runs deterministically.
"""

from __future__ import annotations

import asyncio
import json
import re
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.agents._prompt import session_context_payload
from app.agents.conversation_assistant import conversation_assistant_node
from app.agents.final_response import final_response_node
from app.agents.plan_generator import plan_generator_node
from app.agents.risk_assessor import risk_assessor_node
from app.agents.supervisor import supervisor_node
from app.state import RiskAssessment, RiskLevel


# ── Smart strategies ──────────────────────────────────────────────────────────


# Recent-session-message patterns that would trip conversation_assistant's
# ``_reply_from_recent_session`` heuristic and skip the LLM call altogether.
_ALIAS_SECRET_PATTERNS = (
    re.compile(r"你(?:现在)?叫"),
    re.compile(r"你的名字是"),
    re.compile(r"(?:临时)?口令是"),
    re.compile(r"(?:密码|暗号)是"),
)


def _has_alias_or_secret(content: str) -> bool:
    return any(pattern.search(content) for pattern in _ALIAS_SECRET_PATTERNS)


# Plain printable text without the special substrings that would otherwise
# activate deterministic early-return branches.
_SAFE_TEXT = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Zs"),
        max_codepoint=0x9FFF,
    ),
    min_size=0,
    max_size=40,
).filter(lambda s: not _has_alias_or_secret(s))


def _recent_message_strategy() -> st.SearchStrategy[dict[str, Any]]:
    return st.fixed_dictionaries(
        {
            "role": st.sampled_from(["user", "assistant"]),
            "content": _SAFE_TEXT,
        }
    )


def _snapshot_strategy() -> st.SearchStrategy[dict[str, Any]]:
    return st.fixed_dictionaries(
        {
            "risk_level": st.sampled_from(["none", "low", "moderate", "high", "critical"]),
            "plan_info": st.just({}),
            "query_count": st.integers(min_value=0, max_value=10),
        }
    )


def _long_term_memory_strategy() -> st.SearchStrategy[dict[str, Any]]:
    return st.fixed_dictionaries(
        {
            "type": st.sampled_from(["preference", "fact"]),
            "content": _SAFE_TEXT,
        }
    )


@st.composite
def _memory_context_strategy(draw) -> dict[str, Any]:
    """Generate a ``memory_context`` with ≥1 non-empty top-level field."""
    summary = draw(_SAFE_TEXT)
    recent = draw(st.lists(_recent_message_strategy(), max_size=5))
    snapshot = draw(st.one_of(st.just({}), _snapshot_strategy()))
    long_term = draw(st.lists(_long_term_memory_strategy(), max_size=3))

    # Non-empty invariant: at least one of the four keys is truthy.
    if not (summary or recent or snapshot or long_term):
        summary = draw(_SAFE_TEXT.filter(bool))

    return {
        "conversation_summary": summary,
        "recent_session_messages": recent,
        "business_snapshot": snapshot,
        "long_term_memories": long_term,
    }


# ── Mock LLM plumbing ─────────────────────────────────────────────────────────


def _make_mock_llm(response_content: str = '{"next_agent":"__end__","reasoning":"ok"}') -> SimpleNamespace:
    """Return a mock LLM with ``is_enabled=True`` and a capturing ``ainvoke``."""
    return SimpleNamespace(
        is_enabled=True,
        ainvoke=AsyncMock(return_value=SimpleNamespace(content=response_content)),
    )


def _extract_prompt_payload(mock_llm: SimpleNamespace) -> dict[str, Any]:
    """Decode the first positional arg of the first ``ainvoke`` call as JSON."""
    assert mock_llm.ainvoke.await_count >= 1, "Agent never invoked the LLM"
    call = mock_llm.ainvoke.await_args_list[0]
    prompt = call.args[0]
    assert isinstance(prompt, str), (
        f"Expected JSON-encoded string prompt, got {type(prompt).__name__}"
    )
    return json.loads(prompt)


def _assert_memory_context_matches_state(payload: dict[str, Any], state: dict[str, Any]) -> None:
    assert "memory_context" in payload, (
        f"LLM prompt payload missing top-level 'memory_context' key: keys={list(payload.keys())}"
    )
    expected = session_context_payload(state)
    got = payload["memory_context"]
    assert got == expected, (
        f"memory_context mismatch\nexpected: {expected!r}\n     got: {got!r}"
    )


# ── Property 4: per-agent harnesses ───────────────────────────────────────────


@given(memory_context=_memory_context_strategy())
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_supervisor_prompt_includes_memory_context(memory_context):
    """Feature: ai-session-history-resume, Property 4: memory_context ubiquity

    Validates: Requirements 3.4
    """
    # A water-domain query with no data_summary forces the deterministic route
    # to "data_analyst", which in turn triggers the LLM path in supervisor_node.
    state = {
        "user_query": "当前水情态势如何",
        "messages": [],
        "iteration": 0,
        "memory_context": memory_context,
    }

    async def _run():
        mock_llm = _make_mock_llm()
        with patch("app.agents.supervisor.get_llm", return_value=mock_llm):
            await supervisor_node(state)
        return mock_llm

    mock_llm = asyncio.run(_run())
    payload = _extract_prompt_payload(mock_llm)
    _assert_memory_context_matches_state(payload, state)


@given(memory_context=_memory_context_strategy())
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_conversation_assistant_prompt_includes_memory_context(memory_context):
    """Feature: ai-session-history-resume, Property 4: memory_context ubiquity

    Validates: Requirements 3.4
    """
    # Non-identity, non-recall user_query so the early-return short circuits
    # (identity alias, recent-session secret) are skipped and the LLM runs.
    state = {
        "user_query": "请帮我梳理一下当前水情工作的重点",
        "memory_context": memory_context,
    }

    async def _run():
        mock_llm = _make_mock_llm(response_content="正在为你梳理。")
        with patch("app.agents.conversation_assistant.get_llm", return_value=mock_llm):
            await conversation_assistant_node(state)
        return mock_llm

    mock_llm = asyncio.run(_run())
    payload = _extract_prompt_payload(mock_llm)
    _assert_memory_context_matches_state(payload, state)


@given(memory_context=_memory_context_strategy())
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_risk_assessor_prompt_includes_memory_context(memory_context):
    """Feature: ai-session-history-resume, Property 4: memory_context ubiquity

    Validates: Requirements 3.4
    """
    # risk_assessor only hits the LLM path when overview_data is populated.
    state = {
        "user_query": "评估当前风险",
        "overview_data": {
            "stations": [],
            "active_alarms": [],
        },
        "weather_forecast": {"forecast": {"total_precip_24h_mm": 0}},
        "memory_context": memory_context,
    }

    # Return a minimal valid risk assessment JSON so parsing succeeds; the
    # content is irrelevant to the property being tested.
    response_json = json.dumps(
        {
            "risk_level": "none",
            "risk_score": 0,
            "affected_stations": [],
            "key_risks": ["当前未发现显著风险"],
            "trend": "stable",
            "reasoning": "模型响应",
            "response_level": "常态监测",
        },
        ensure_ascii=False,
    )

    async def _run():
        mock_llm = _make_mock_llm(response_content=response_json)
        with patch("app.agents.risk_assessor.get_llm", return_value=mock_llm):
            await risk_assessor_node(state)
        return mock_llm

    mock_llm = asyncio.run(_run())
    payload = _extract_prompt_payload(mock_llm)
    _assert_memory_context_matches_state(payload, state)


@given(memory_context=_memory_context_strategy())
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_plan_generator_prompt_includes_memory_context(memory_context):
    """Feature: ai-session-history-resume, Property 4: memory_context ubiquity

    Validates: Requirements 3.4
    """
    state = {
        "user_query": "生成防汛预案",
        "risk_assessment": RiskAssessment(
            risk_level=RiskLevel.MODERATE,
            risk_score=45.0,
            key_risks=["持续降雨"],
        ),
        "data_summary": "已汇总当前监测数据",
        "session_id": "s-test",
        "memory_context": memory_context,
    }

    # Return empty JSON so the harness rejects it and the fallback plan is
    # used — we only care that ainvoke was called with the canonical payload.
    async def _run():
        mock_llm = _make_mock_llm(response_content="{}")
        with patch("app.agents.plan_generator.get_llm", return_value=mock_llm):
            await plan_generator_node(state)
        return mock_llm

    mock_llm = asyncio.run(_run())
    payload = _extract_prompt_payload(mock_llm)
    _assert_memory_context_matches_state(payload, state)


@given(memory_context=_memory_context_strategy())
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_final_response_prompt_includes_memory_context(memory_context):
    """Feature: ai-session-history-resume, Property 4: memory_context ubiquity

    Validates: Requirements 3.4
    """
    # intent=risk_assessment with an assessment but no draft / plan / data_only
    # → final_response_node enters the LLM rewrite branch.
    state = {
        "intent": "risk_assessment",
        "user_query": "评估当前风险",
        "risk_assessment": RiskAssessment(
            risk_level=RiskLevel.NONE,
            risk_score=0.0,
            key_risks=["暂无显著风险"],
        ),
        "memory_context": memory_context,
    }

    async def _run():
        # Any string is fine — harness will reject non-JSON and fall back, but
        # the first ainvoke call is still recorded.
        mock_llm = _make_mock_llm(response_content="not-json")
        with patch("app.agents.final_response.get_llm", return_value=mock_llm):
            await final_response_node(state)
        return mock_llm

    mock_llm = asyncio.run(_run())
    payload = _extract_prompt_payload(mock_llm)
    _assert_memory_context_matches_state(payload, state)
