"""Shared prompt construction helpers for LLM-invoking agents.

This module centralises the canonical shape of the ``memory_context`` payload
that every agent must inject into its LLM prompt when the graph is resumed from
a historical session. Keeping the shape in one place lets us enforce the
invariant (Property 4 in ``ai-session-history-resume`` design) via a single
property-based test instead of sprinkling ad-hoc assertions in each agent.
"""

from __future__ import annotations

from typing import Any

from app.state import to_plain_data

__all__ = ["session_context_payload"]


# Keys expected in ``state['memory_context']`` when it has been populated by
# ``MemoryContext.to_prompt_context`` (see ``app/memory/models.py``).
_SUMMARY_KEY = "conversation_summary"
_RECENT_MESSAGES_KEY = "recent_session_messages"
_SNAPSHOT_KEY = "business_snapshot"
_LONG_TERM_MEMORIES_KEY = "long_term_memories"


def session_context_payload(state: dict[str, Any] | None) -> dict[str, Any]:
    """Return the canonical memory payload for an LLM prompt.

    The returned dict always contains the four top-level keys expected by the
    prompts of every LLM-invoking agent:

    - ``conversation_summary`` (str): rolling summary of the conversation,
      defaulting to ``""`` when absent.
    - ``recent_session_messages`` (list): recent ``user``/``assistant`` turns
      for short-term memory, defaulting to ``[]`` when absent.
    - ``business_snapshot`` (dict): latest structured snapshot (risk level,
      plan info, etc.), defaulting to ``{}`` when absent.
    - ``long_term_memories`` (list): long-term cross-session memory items,
      defaulting to ``[]`` when absent.

    The payload is produced via ``to_plain_data`` so that it is a deep-copy of
    the underlying state and is guaranteed to be JSON-serialisable before being
    embedded into a prompt. Callers may therefore mutate the returned dict
    without affecting ``state['memory_context']``.
    """

    memory_context: Any = None
    if isinstance(state, dict):
        memory_context = state.get("memory_context")

    if not isinstance(memory_context, dict):
        memory_context = {}

    summary = memory_context.get(_SUMMARY_KEY, "")
    if not isinstance(summary, str):
        summary = ""

    recent_messages = memory_context.get(_RECENT_MESSAGES_KEY, [])
    if not isinstance(recent_messages, list):
        recent_messages = []

    snapshot = memory_context.get(_SNAPSHOT_KEY, {})
    if not isinstance(snapshot, dict):
        snapshot = {}

    long_term_memories = memory_context.get(_LONG_TERM_MEMORIES_KEY, [])
    if not isinstance(long_term_memories, list):
        long_term_memories = []

    payload: dict[str, Any] = {
        _SUMMARY_KEY: summary,
        _RECENT_MESSAGES_KEY: recent_messages,
        _SNAPSHOT_KEY: snapshot,
        _LONG_TERM_MEMORIES_KEY: long_term_memories,
    }

    # ``to_plain_data`` recursively walks the structure, returning fresh dicts
    # and lists. This both deep-copies (caller isolation) and guarantees the
    # payload is JSON-serialisable (Enums -> values, datetimes -> isoformat,
    # dataclasses -> dicts, Decimals -> int/float).
    return to_plain_data(payload)
