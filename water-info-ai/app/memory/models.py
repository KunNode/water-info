"""Typed memory contracts for session and long-term recall."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    FACT = "fact"
    PREFERENCE = "preference"
    DECISION = "decision"
    OPERATION = "operation"
    TODO = "todo"


@dataclass
class MemoryCandidate:
    item_type: MemoryType = MemoryType.FACT
    content: str = ""
    importance: float = 0.5
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemorySearchResult:
    id: int | None = None
    namespace: str = ""
    item_type: str = MemoryType.FACT.value
    content: str = ""
    importance: float = 0.5
    confidence: float = 0.5
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source_session_id: str = ""
    updated_at: str | None = None


@dataclass
class MemoryContext:
    summary: str = ""
    recent_messages: list[dict[str, str]] = field(default_factory=list)
    memories: list[MemorySearchResult] = field(default_factory=list)
    snapshot: dict[str, Any] | None = None

    def to_prompt_context(self) -> dict[str, Any]:
        return {
            "conversation_summary": self.summary,
            "recent_session_messages": self.recent_messages,
            "long_term_memories": [
                {
                    "type": item.item_type,
                    "content": item.content,
                    "importance": item.importance,
                    "confidence": item.confidence,
                    "source_session_id": item.source_session_id,
                    "updated_at": item.updated_at,
                }
                for item in self.memories
            ],
            "business_snapshot": self.snapshot or {},
        }
