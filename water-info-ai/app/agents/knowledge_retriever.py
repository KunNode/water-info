"""Knowledge agent: sole owner of RAG retrieval.

Two modes selected by ``rag_target`` in state:
- ``answer``: synthesize a knowledge-base-grounded reply and terminate the run.
- ``preflight_plan`` / ``preflight_risk``: retrieve only, populate
  ``evidence_context`` for a downstream agent, and return to supervisor.
"""

from __future__ import annotations

import hashlib
import json

from app.config import get_settings
from app.rag.service import build_evidence, format_evidence_markdown, search_knowledge_base
from app.services.llm import get_llm


def _normalize_query_hash(query: str) -> str:
    return hashlib.sha1(query.strip().lower().encode("utf-8")).hexdigest()


async def knowledge_retriever_node(state: dict) -> dict:
    settings = get_settings()
    query = str(state.get("user_query", "")).strip()
    rag_target = str(state.get("rag_target") or "answer")
    cache: dict = dict(state.get("rag_query_cache") or {})
    skip_reasons: list[str] = list(state.get("rag_skip_reasons") or [])
    call_count = int(state.get("rag_call_count", 0))

    query_hash = _normalize_query_hash(query) if query else ""
    cached_results = cache.get(query_hash) if query_hash else None

    if cached_results is not None:
        results = cached_results
        skip_reasons.append(f"cache_hit:{rag_target}")
    elif not query:
        results = []
        skip_reasons.append("empty_query")
    elif call_count >= settings.rag_max_calls_per_session:
        results = []
        skip_reasons.append(f"budget_exhausted:{call_count}")
    else:
        top_k = settings.rag_top_k if rag_target == "answer" else max(3, settings.rag_top_k - 1)
        results = await search_knowledge_base(query, top_k=top_k)
        call_count += 1
        if query_hash:
            cache[query_hash] = results
        if not results:
            skip_reasons.append("no_results")

    evidence = build_evidence(results)

    update: dict = {
        "current_agent": "knowledge_retriever",
        "evidence_context": evidence,
        "evidence": evidence,
        "rag_call_count": call_count,
        "rag_query_cache": cache,
        "rag_skip_reasons": skip_reasons,
        "rag_target": rag_target,
    }

    if rag_target != "answer":
        # Preflight grounding: hand evidence back to supervisor; downstream agent will use it.
        message = (
            f"已为下一步检索到 {len(evidence)} 条参考依据。"
            if evidence
            else "知识库未命中，下一步将不依赖知识引用。"
        )
        update["messages"] = [{"role": "knowledge_retriever", "content": message}]
        return update

    # Answer mode: synthesize a final reply with citations.
    reply = "未命中知识库，我暂时没有找到可直接引用的制度、手册或资料。"
    if evidence:
        reply = f"我先从知识库里找到了几段最相关的依据。\n\n{format_evidence_markdown(evidence)}"

    llm = get_llm()
    if llm.is_enabled:
        try:
            response = await llm.ainvoke(
                json.dumps(
                    {
                        "user_query": query,
                        "evidence": [item.__dict__ for item in evidence],
                        "fallback_reply": reply,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                system_prompt=(
                    "你是水务知识库问答助手。"
                    "请仅根据 evidence 回答，引用格式必须使用 [1][2] 这类编号。"
                    "如果 evidence 为空，必须明确说“未命中知识库”，不要编造。"
                    "输出 Markdown。"
                ),
                temperature=0.1,
            )
            content = getattr(response, "content", "").strip()
            if content:
                reply = content
        except Exception:
            pass

    update["final_response"] = reply
    update["messages"] = [{"role": "knowledge_retriever", "content": reply}]
    return update
