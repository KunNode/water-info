"""Knowledge retrieval tools."""

from __future__ import annotations

from app.rag.service import search_knowledge_base
from app.tools.simple_tool import SimpleTool


async def knowledge_search(query: str, top_k: int = 5, doc_types: list[str] | None = None) -> list[dict]:
    """Search the knowledge base and return evidence candidates."""
    return await search_knowledge_base(query, top_k=top_k, source_types=doc_types)


async def _knowledge_search_tool(payload: dict) -> str:
    import json

    results = await knowledge_search(
        str(payload.get("query") or ""),
        top_k=int(payload.get("top_k") or 5),
        doc_types=payload.get("doc_types"),
    )
    return json.dumps(results, ensure_ascii=False)


knowledge_tools = [SimpleTool("knowledge_search", _knowledge_search_tool)]
