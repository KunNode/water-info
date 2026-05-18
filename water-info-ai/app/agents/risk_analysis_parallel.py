"""Parallel risk analysis node.

Runs risk_assessor and knowledge_retriever concurrently when both are needed.
knowledge_retriever runs in preflight mode (retrieval only, no answer synthesis).
"""

from __future__ import annotations

import asyncio

from loguru import logger

from app.agents.knowledge_retriever import knowledge_retriever_node
from app.agents.risk_assessor import risk_assessor_node
from app.state import FloodResponseState
from app.utils.timeout import with_timeout


@with_timeout(180)
async def risk_analysis_parallel_node(state: FloodResponseState) -> dict:
    """Run risk_assessor and knowledge_retriever concurrently."""
    logger.info("Starting parallel risk analysis + knowledge retrieval")

    # Force knowledge_retriever into preflight mode (retrieval only).
    # In this parallel context, risk_assessor owns the analysis —
    # knowledge_retriever should only supply evidence, not synthesize an answer.
    parallel_state = {**state, "rag_target": "preflight_risk"}

    tasks = {
        "risk": asyncio.create_task(risk_assessor_node(state)),
        "knowledge": asyncio.create_task(knowledge_retriever_node(parallel_state)),
    }

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    names = list(tasks.keys())

    merged: dict = {
        "current_agent": "risk_analysis_parallel",
        "messages": [{"role": "risk_analysis_parallel", "content": "并行风险分析完成"}],
    }

    for name, result in zip(names, results):
        if isinstance(result, Exception):
            logger.warning(f"{name} parallel execution failed: {result}")
        elif isinstance(result, dict):
            for key, value in result.items():
                if key == "messages":
                    merged.setdefault("messages", []).extend(value)
                elif key not in merged or not merged[key]:
                    merged[key] = value

    logger.info("Parallel risk analysis complete")
    return merged
