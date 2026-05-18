"""OpenAI-compatible LLM service with streaming support."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, AsyncIterator

import httpx

from app.config import get_settings
from app.observability.otel import llm_span

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    content: str


class OpenAICompatibleLLM:
    def __init__(self) -> None:
        self._settings = get_settings()
        # Shared client — reused across all calls to avoid per-call TCP/TLS overhead
        self._client = httpx.AsyncClient(timeout=self._settings.llm_timeout)

    @property
    def is_enabled(self) -> bool:
        return bool(self._settings.openai_api_key)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def ainvoke(
        self,
        prompt: Any,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        response_format: dict | None = None,
        timeout: float | None = None,
    ) -> SimpleNamespace:
        if not self.is_enabled:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        url = f"{self._settings.openai_api_base.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self._settings.openai_model,
            "messages": self._build_messages(prompt, system_prompt),
            "temperature": temperature,
            "stream": False,
            # Disable extended thinking/reasoning to reduce latency (Qwen3, etc.)
            "enable_thinking": False,
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        with llm_span(self._settings.openai_model, temperature):
            response = await self._client.post(
                url, headers=headers, json=payload,
                timeout=timeout or self._settings.llm_timeout,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                logger.warning(
                    "LLM request failed: status=%s model=%s base=%s body=%s",
                    response.status_code,
                    self._settings.openai_model,
                    self._settings.openai_api_base,
                    response.text[:500],
                )
                raise
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

    async def astream(
        self,
        prompt: Any,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        response_format: dict | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[str]:
        """Stream LLM response token by token."""
        if not self.is_enabled:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        url = f"{self._settings.openai_api_base.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self._settings.openai_model,
            "messages": self._build_messages(prompt, system_prompt),
            "temperature": temperature,
            "stream": True,
            "enable_thinking": False,
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        with llm_span(self._settings.openai_model, temperature):
            async with self._client.stream(
                "POST", url, headers=headers, json=payload,
                timeout=timeout or self._settings.llm_timeout,
            ) as response:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError:
                    logger.warning(
                        "LLM stream request failed: status=%s model=%s",
                        response.status_code, self._settings.openai_model,
                    )
                    raise

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    def _build_messages(self, prompt: Any, system_prompt: str | None) -> list[dict]:
        if isinstance(prompt, list):
            messages = prompt
        else:
            if isinstance(prompt, (dict, list)):
                # Compact JSON — no indent to reduce token count
                prompt = json.dumps(prompt, ensure_ascii=False)
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
