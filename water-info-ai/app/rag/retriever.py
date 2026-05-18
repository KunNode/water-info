"""Hybrid retrieval against the knowledge base."""

from __future__ import annotations

import logging
from collections import defaultdict

from app.config import get_settings
from app.database import get_db_service
from app.rag.embedder import get_embedding_client
from app.rag.models import MetadataFilter, SearchResult, metadata_matches_filter
from app.rag.query_rewriter import rewrite_query
from app.rag.reranker import rerank_results
from app.rag.splitter import segment_search_text

logger = logging.getLogger(__name__)


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
    metadata_filter: MetadataFilter | None = None,
    enable_query_rewriting: bool = True,
) -> list[SearchResult]:
    query = query.strip()
    if not query:
        return []

    db = get_db_service()
    settings = get_settings()
    vector_rows: list[dict] = []
    keyword_rows: list[dict] = []
    embed_client = get_embedding_client()

    # Query rewriting for improved recall
    queries = [query]
    if enable_query_rewriting:
        try:
            queries = await rewrite_query(query, max_variants=3)
            if len(queries) > 1:
                logger.info("Query rewriting: '%s' -> %d variants", query[:50], len(queries))
        except Exception as e:
            logger.warning("Query rewriting failed, using original: %s", str(e))
            queries = [query]

    # Search with original and rewritten queries
    all_vector_rows: list[dict] = []
    all_keyword_rows: list[dict] = []

    for q in queries:
        if embed_client.is_enabled:
            try:
                query_embedding = (await embed_client.embed_texts([q]))[0]
                rows = await db.vector_search_kb(
                    query_embedding,
                    top_n=max(top_k * 4, 20),
                    source_types=source_types,
                    model=settings.embedding_model,
                    metadata_filter=metadata_filter,
                )
                all_vector_rows.extend(rows)
            except Exception:
                pass

        tokenized_query = segment_search_text(q)
        if tokenized_query:
            rows = await db.keyword_search_kb(
                tokenized_query,
                top_n=max(top_k * 4, 20),
                source_types=source_types,
                metadata_filter=metadata_filter,
            )
            all_keyword_rows.extend(rows)

    # Deduplicate rows by chunk_id
    vector_rows = _deduplicate_rows(all_vector_rows)
    keyword_rows = _deduplicate_rows(all_keyword_rows)

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
        result = SearchResult(
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
        if not metadata_matches_filter(result, metadata_filter):
            continue
        results.append(result)
        per_document[document_id] += 1
        if len(results) >= top_k:
            break

    # Apply re-ranking if enabled
    settings = get_settings()
    if settings.rag_reranker_enabled and results:
        results = await rerank_results(query, results, top_k=top_k)

    return results


def _deduplicate_rows(rows: list[dict]) -> list[dict]:
    """Deduplicate rows by chunk_id, keeping the first occurrence."""
    seen = set()
    deduplicated = []
    for row in rows:
        chunk_id = str(row.get("chunk_id", ""))
        if chunk_id not in seen:
            seen.add(chunk_id)
            deduplicated.append(row)
    return deduplicated
