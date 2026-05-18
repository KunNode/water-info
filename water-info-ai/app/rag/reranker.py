"""Re-ranker for improving RAG retrieval quality."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import get_settings
from app.rag.models import SearchResult
from app.services.llm import get_llm

logger = logging.getLogger(__name__)


async def rerank_results(
    query: str,
    results: list[SearchResult],
    top_k: int = 5,
) -> list[SearchResult]:
    """Re-rank search results using LLM-based semantic scoring.

    Uses a lightweight LLM call to score each result's relevance to the query.
    Falls back to original ranking if LLM is unavailable or fails.
    """
    if not results or len(results) <= top_k:
        return results

    settings = get_settings()
    if not settings.rag_reranker_enabled:
        return results[:top_k]

    llm = get_llm()
    if not llm.is_enabled:
        return results[:top_k]

    try:
        # Prepare documents for scoring
        doc_summaries = []
        for i, result in enumerate(results[:10]):  # Limit to top 10 for efficiency
            doc_summaries.append({
                "index": i,
                "title": result.document_title,
                "content": result.content[:300],  # Truncate for efficiency
                "heading": " / ".join(result.heading_path) if result.heading_path else "",
            })

        # Ask LLM to score relevance
        prompt = f"""请评估以下文档与查询的相关性，给出 1-10 的分数。

查询：{query}

文档列表：
{json.dumps(doc_summaries, ensure_ascii=False, indent=2)}

请返回 JSON 数组，每个元素包含 index 和 score（1-10）：
[{{"index": 0, "score": 8}}, ...]"""

        response = await llm.ainvoke(
            prompt,
            system_prompt="你是文档相关性评估专家。请根据查询与文档内容的语义相关性打分。",
            temperature=0.1,
            response_format={"type": "json_object"},
            max_retries=1,
        )

        # Parse scores
        content = response.content.strip()
        scores = json.loads(content)

        # Apply scores to results
        scored_results = []
        for score_item in scores:
            idx = score_item.get("index", 0)
            score = score_item.get("score", 5)
            if 0 <= idx < len(results):
                result = results[idx]
                # Adjust score based on LLM rating
                adjusted_score = result.score * (score / 5.0)  # Normalize around original score
                scored_results.append((adjusted_score, result))

        # Sort by adjusted score
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [result for _, result in scored_results[:top_k]]

    except Exception as e:
        logger.warning("Re-ranking failed, using original order: %s", str(e))
        return results[:top_k]
