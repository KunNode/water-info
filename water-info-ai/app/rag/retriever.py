"""Hybrid retrieval against the knowledge base."""

from __future__ import annotations

from collections import defaultdict

from app.config import get_settings
from app.database import get_db_service
from app.rag.embedder import get_embedding_client
from app.rag.models import SearchResult
from app.rag.splitter import segment_search_text


def _merge_row(base: dict | None, row: dict) -> dict:
    if not base:
        return dict(row)
    merged = dict(base)
    merged.update({key: value for key, value in row.items() if value is not None})
    return merged


async def hybrid_search(
    query: str,
    *,
    top_k: int = 5,
    source_types: list[str] | None = None,
) -> list[SearchResult]:
    query = query.strip()
    if not query:
        return []

    db = get_db_service()
    settings = get_settings()
    vector_rows: list[dict] = []
    keyword_rows: list[dict] = []
    embed_client = get_embedding_client()

    if embed_client.is_enabled:
        try:
            query_embedding = (await embed_client.embed_texts([query]))[0]
            vector_rows = await db.vector_search_kb(
                query_embedding,
                top_n=max(top_k * 4, 20),
                source_types=source_types,
                model=settings.embedding_model,
            )
        except Exception:
            vector_rows = []

    tokenized_query = segment_search_text(query)
    if tokenized_query:
        keyword_rows = await db.keyword_search_kb(
            tokenized_query,
            top_n=max(top_k * 4, 20),
            source_types=source_types,
        )

    if not vector_rows and not keyword_rows:
        return []

    scored: dict[str, dict] = {}
    fusion_scores: defaultdict[str, float] = defaultdict(float)

    for rank, row in enumerate(vector_rows, start=1):
        chunk_id = str(row["chunk_id"])
        scored[chunk_id] = _merge_row(scored.get(chunk_id), row)
        fusion_scores[chunk_id] += 1 / (60 + rank)
    for rank, row in enumerate(keyword_rows, start=1):
        chunk_id = str(row["chunk_id"])
        scored[chunk_id] = _merge_row(scored.get(chunk_id), row)
        fusion_scores[chunk_id] += 1 / (60 + rank)

    ordered = sorted(
        scored.values(),
        key=lambda row: (
            fusion_scores[str(row["chunk_id"])],
            float(row.get("vector_score") or 0.0),
            float(row.get("keyword_score") or 0.0),
        ),
        reverse=True,
    )

    results: list[SearchResult] = []
    per_document: defaultdict[str, int] = defaultdict(int)
    for row in ordered:
        document_id = str(row["document_id"])
        if per_document[document_id] >= 3:
            continue
        vector_score = row.get("vector_score")
        keyword_score = row.get("keyword_score")
        effective_score = float(vector_score or keyword_score or fusion_scores[str(row["chunk_id"])])
        if vector_score is not None and effective_score < settings.rag_min_score:
            continue
        results.append(
            SearchResult(
                chunk_id=str(row["chunk_id"]),
                document_id=document_id,
                document_title=str(row["document_title"]),
                source_uri=str(row.get("source_uri") or ""),
                content=str(row.get("content") or ""),
                heading_path=list(row.get("heading_path") or []),
                score=effective_score,
                vector_score=float(vector_score) if vector_score is not None else None,
                keyword_score=float(keyword_score) if keyword_score is not None else None,
                metadata=dict(row.get("metadata") or {}),
            )
        )
        per_document[document_id] += 1
        if len(results) >= top_k:
            break

    return results
