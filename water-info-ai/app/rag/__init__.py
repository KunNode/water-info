"""RAG services for knowledge ingestion and retrieval."""

from app.rag.service import (
    build_evidence,
    format_evidence_markdown,
    get_knowledge_base_service,
    search_knowledge_base,
)

__all__ = [
    "build_evidence",
    "format_evidence_markdown",
    "get_knowledge_base_service",
    "search_knowledge_base",
]
