"""Core RAG data structures."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextBlock:
    text: str
    heading_path: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class LoadedDocument:
    title: str
    mime: str
    raw_text: str
    blocks: list[TextBlock] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ChunkCandidate:
    chunk_index: int
    content: str
    token_count: int
    heading_path: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    search_text: str = ""


@dataclass
class SearchResult:
    chunk_id: str
    document_id: str
    document_title: str
    source_uri: str
    content: str
    heading_path: list[str] = field(default_factory=list)
    score: float = 0.0
    vector_score: float | None = None
    keyword_score: float | None = None
    metadata: dict = field(default_factory=dict)
