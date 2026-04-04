"""OpenAI-compatible non-streaming LLM service."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    content: str


class OpenAICompatibleLLM:
    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def is_enabled(self) -> bool:
        return bool(self._settings.openai_api_key)

    async def ainvoke(
        self,
        prompt: Any,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        response_format: dict | None = None,
    ) -> SimpleNamespace:
        if not self.is_enabled:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        url = f"{self._settings.openai_api_base.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self._settings.openai_model,
            "messages": self._build_messages(prompt, system_prompt),
            "temperature": temperature,
            "stream": False,
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._settings.llm_timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if isinstance(content, list):
            content = "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return SimpleNamespace(content=str(content))

    def _build_messages(self, prompt: Any, system_prompt: str | None) -> list[dict]:
        if isinstance(prompt, list):
            messages = prompt
        else:
            if isinstance(prompt, (dict, list)):
                prompt = json.dumps(prompt, ensure_ascii=False, indent=2)
            else:
                prompt = str(prompt)
            messages = [{"role": "user", "content": prompt}]

        if system_prompt:
            return [{"role": "system", "content": system_prompt}, *messages]
        return messages


_llm: OpenAICompatibleLLM | None = None


def get_llm() -> OpenAICompatibleLLM:
    global _llm
    if _llm is None:
        _llm = OpenAICompatibleLLM()
    return _llm
