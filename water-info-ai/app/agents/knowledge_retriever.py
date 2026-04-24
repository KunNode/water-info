"""Knowledge-oriented answer node."""

from __future__ import annotations

import json

from app.rag.service import build_evidence, format_evidence_markdown, search_knowledge_base
from app.services.llm import get_llm


async def knowledge_retriever_node(state: dict) -> dict:
    query = str(state.get("user_query", "")).strip()
    results = await search_knowledge_base(query, top_k=5)
    evidence = build_evidence(results)

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

    return {
        "current_agent": "knowledge_retriever",
        "evidence": evidence,
        "final_response": reply,
        "messages": [{"role": "knowledge_retriever", "content": reply}],
    }
