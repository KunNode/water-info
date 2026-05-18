"""State pruning node to prevent unbounded growth of graph state."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default thresholds
MAX_MESSAGES = 20
MAX_EXECUTION_TRACES = 50


def _prune_messages(messages: list[dict], max_count: int = MAX_MESSAGES) -> list[dict]:
    """Keep only the most recent messages, preserving system and user messages."""
    if len(messages) <= max_count:
        return messages

    # Keep the most recent messages
    pruned = messages[-max_count:]
    logger.info("Pruned messages from %d to %d", len(messages), len(pruned))
    return pruned


def _prune_execution_traces(traces: list[dict], max_count: int = MAX_EXECUTION_TRACES) -> list[dict]:
    """Keep only the most recent execution traces."""
    if len(traces) <= max_count:
        return traces

    # Keep the most recent traces
    pruned = traces[-max_count:]
    logger.info("Pruned execution_traces from %d to %d", len(traces), len(pruned))
    return pruned


def _clear_temporary_fields(state: dict) -> dict:
    """Clear temporary fields that are only needed for the current turn."""
    fields_to_clear = [
        "rag_skip_reasons",
        "rag_query_cache",
    ]
    cleared = {}
    for field in fields_to_clear:
        if field in state:
            cleared[field] = [] if isinstance(state[field], list) else {}
    return cleared


async def state_pruner_node(state: dict) -> dict:
    """Prune state to prevent unbounded growth.

    This node is called after memory_writer to clean up the state:
    - Trim messages to the most recent N
    - Trim execution_traces to the most recent M
    - Clear temporary fields that are only needed for the current turn
    """
    updates: dict[str, Any] = {}

    # Prune messages
    messages = state.get("messages", [])
    if len(messages) > MAX_MESSAGES:
        updates["messages"] = _prune_messages(messages)

    # Prune execution traces
    traces = state.get("execution_traces", [])
    if len(traces) > MAX_EXECUTION_TRACES:
        updates["execution_traces"] = _prune_execution_traces(traces)

    # Clear temporary fields
    updates.update(_clear_temporary_fields(state))

    if updates:
        logger.info("State pruner applied: %s", list(updates.keys()))

    return updates
