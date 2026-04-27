"""Chunking helpers for RAG ingestion."""

from __future__ import annotations

import re

from app.rag.models import ChunkCandidate, LoadedDocument

try:
    import jieba
except ImportError:  # pragma: no cover - dependency is optional for tests
    jieba = None

try:
    import tiktoken
except ImportError:  # pragma: no cover - dependency is optional for tests
    tiktoken = None

_ENCODER = None
if tiktoken is not None:  # pragma: no branch
    try:
        _ENCODER = tiktoken.get_encoding("cl100k_base")
    except Exception:  # pragma: no cover - fallback path
        _ENCODER = None


def count_tokens(text: str) -> int:
    if _ENCODER is not None:
        return len(_ENCODER.encode(text))
    return max(1, len(text) // 3)


def _tail_overlap(text: str, overlap_tokens: int) -> str:
    if overlap_tokens <= 0:
        return ""
    if _ENCODER is not None:
        tokens = _ENCODER.encode(text)
        if not tokens:
            return ""
        return _ENCODER.decode(tokens[-overlap_tokens:])
    return text[-overlap_tokens * 3 :]


def _split_long_text(text: str, target_tokens: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if count_tokens(text) <= target_tokens:
        return [text]

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[。！？；\.\!\?])\s+", text.replace("\n", " "))
        if sentence.strip()
    ]
    if len(sentences) <= 1:
        return [text[i : i + max(target_tokens * 3, 300)] for i in range(0, len(text), max(target_tokens * 3, 300))]

    parts: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if current and count_tokens(candidate) > target_tokens:
            parts.append(current.strip())
            current = sentence
            continue
        current = candidate
    if current.strip():
        parts.append(current.strip())
    return parts


def segment_search_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return ""
    if jieba is None:
        return normalized
    return " ".join(token.strip() for token in jieba.lcut_for_search(normalized) if token.strip())


def split_loaded_document(
    loaded: LoadedDocument,
    *,
    target_tokens: int = 500,
    overlap_tokens: int = 80,
) -> list[ChunkCandidate]:
    chunks: list[ChunkCandidate] = []
    current_parts: list[str] = []
    current_tokens = 0
    current_heading: list[str] = []
    current_metadata: dict = {}

    def flush() -> None:
        nonlocal current_parts, current_tokens, current_heading, current_metadata
        content = "\n\n".join(part.strip() for part in current_parts if part.strip()).strip()
        if not content:
            current_parts = []
            current_tokens = 0
            current_heading = []
            current_metadata = {}
            return
        chunks.append(
            ChunkCandidate(
                chunk_index=len(chunks),
                content=content,
                token_count=count_tokens(content),
                heading_path=list(current_heading),
                metadata=dict(current_metadata),
                search_text=segment_search_text(content),
            )
        )
        overlap = _tail_overlap(content, overlap_tokens)
        current_parts = [overlap] if overlap else []
        current_tokens = count_tokens(overlap) if overlap else 0
        current_heading = list(current_heading)
        current_metadata = dict(current_metadata)

    for block in loaded.blocks:
        segments = _split_long_text(block.text, target_tokens)
        for segment in segments:
            segment_tokens = count_tokens(segment)
            if current_parts and current_tokens + segment_tokens > target_tokens:
                flush()
            if not current_parts:
                current_heading = list(block.heading_path)
                current_metadata = dict(block.metadata)
            current_parts.append(segment)
            current_tokens += segment_tokens

    flush()
    return chunks
