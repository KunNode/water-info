"""Direct LLM streaming client — no LangChain dependency."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def stream_completion(messages: list[dict], temperature: float = 0.3) -> AsyncIterator[str]:
    """Yield text tokens from an OpenAI-compatible streaming chat endpoint."""
    settings = get_settings()
    if not settings.openai_api_key:
        yield _fallback_message()
        return

    url = f"{settings.openai_api_base.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openai_model,
        "messages": messages,
        "stream": True,
        "temperature": temperature,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    except Exception as exc:
        logger.warning("LLM stream failed: %s", exc)
        yield _fallback_message()


def _fallback_message() -> str:
    return (
        "\n> ⚠️ 未配置 LLM API Key，以下为基于规则引擎生成的结构化报告。\n"
        "> 请在环境变量中设置 OPENAI_API_KEY 以启用 AI 分析。\n"
    )
