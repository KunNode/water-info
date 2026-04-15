"""LLM 实例工厂"""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import get_settings


@lru_cache
def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    """获取 ChatOpenAI 实例（兼容 OpenAI API 格式的任意后端）"""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.openai_api_key,
        temperature=temperature,
        max_tokens=4096,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
    )


def get_creative_llm() -> ChatOpenAI:
    """获取较高创造性的 LLM（用于生成预案文本）"""
    return get_llm(temperature=0.3)
