from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agents._contract import AgentContract, register


class KnowledgeRetrieverIn(BaseModel):
    user_query: str


class KnowledgeRetrieverOut(BaseModel):
    evidence_context: list[Any] = []
    evidence: list[Any] = []
    rag_call_count: int = 0
    rag_query_cache: dict[str, Any] = {}
    rag_skip_reasons: list[str] = []
    rag_target: str = ""


register(AgentContract(
    agent_name="knowledge_retriever",
    input_model=KnowledgeRetrieverIn,
    output_model=KnowledgeRetrieverOut,
    required_input_keys=["user_query"],
))
