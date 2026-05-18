"""Query rewriting for improved RAG retrieval."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.llm import get_llm

logger = logging.getLogger(__name__)

# Domain-specific synonyms for flood management
DOMAIN_SYNONYMS = {
    "防汛": ["防洪", "抗洪", "防涝"],
    "水位": ["水位线", "水面高度", "水位高程"],
    "警戒": ["预警", "警报", "告警"],
    "Ⅳ级": ["四级", "4级"],
    "Ⅲ级": ["三级", "3级"],
    "Ⅱ级": ["二级", "2级"],
    "Ⅰ级": ["一级", "1级"],
    "响应": ["应急响应", "响应行动"],
    "水库": ["库区", "蓄水区"],
    "堤防": ["堤坝", "防洪堤"],
    "泵站": ["排水站", "抽水站"],
    "流量": ["径流量", "水流速"],
    "降雨": ["降水", "下雨"],
    "预警": ["警报", "告警", "警戒"],
}


def _generate_keyword_variants(query: str) -> list[str]:
    """Generate query variants using domain-specific synonyms."""
    variants = []
    for term, synonyms in DOMAIN_SYNONYMS.items():
        if term in query:
            for synonym in synonyms:
                variants.append(query.replace(term, synonym))
    return variants[:2]  # Limit to 2 variants


async def rewrite_query(query: str, max_variants: int = 3) -> list[str]:
    """Rewrite query to generate multiple search variants.

    Returns a list of queries including the original and rewritten variants.
    Uses a two-layer approach:
    1. Fast path: keyword synonym expansion (0ms)
    2. Fallback: LLM-based query rewriting for semantic understanding
    """
    queries = [query]

    # Layer 1: Fast keyword synonym expansion
    keyword_variants = _generate_keyword_variants(query)
    queries.extend(keyword_variants)

    # Layer 2: LLM-based rewriting if we need more variants
    if len(queries) < max_variants:
        llm = get_llm()
        if llm.is_enabled:
            try:
                llm_variants = await _llm_rewrite(query, max_variants - len(queries))
                queries.extend(llm_variants)
            except Exception as e:
                logger.warning("LLM query rewriting failed: %s", str(e))

    # Deduplicate while preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        q_normalized = q.strip()
        if q_normalized and q_normalized not in seen:
            seen.add(q_normalized)
            unique_queries.append(q_normalized)

    return unique_queries[:max_variants]


async def _llm_rewrite(query: str, max_variants: int) -> list[str]:
    """Use LLM to generate semantically equivalent query variants."""
    prompt = f"""请为以下防汛领域查询生成 {max_variants} 个语义等价的搜索变体。

要求：
1. 保留原始查询的核心含义
2. 使用不同的表达方式（如同义词、缩写、口语化表达）
3. 适用于防汛、水利、水文领域的知识库检索
4. 每个变体单独一行，不要编号

原始查询：{query}

变体："""

    try:
        response = await get_llm().ainvoke(
            prompt,
            system_prompt="你是防汛领域的查询改写专家。请生成语义等价的搜索变体，用于知识库检索。",
            temperature=0.3,
            max_retries=1,
        )
        content = response.content.strip()
        variants = [line.strip() for line in content.split("\n") if line.strip()]
        return variants[:max_variants]
    except Exception as e:
        logger.warning("LLM query rewrite failed: %s", str(e))
        return []
