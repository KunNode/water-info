"""OpenAI-compatible LLM service with streaming support."""

from __future__ import annotations

import asyncio
import json
import logging
import time
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


class CircuitBreaker:
    """Simple circuit breaker to prevent requests to a failing LLM endpoint."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._state = "closed"  # closed, open, half-open

    @property
    def is_open(self) -> bool:
        if self._state == "open":
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = "half-open"
                return False
            return True
        return False

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            logger.warning("Circuit breaker opened after %d failures", self._failure_count)


# Global circuit breaker instance
_circuit_breaker = CircuitBreaker()


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
        max_retries: int = 3,
    ) -> SimpleNamespace:
        if not self.is_enabled:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        if _circuit_breaker.is_open:
            raise RuntimeError("LLM circuit breaker is open, requests temporarily blocked")

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

        last_exception = None
        for attempt in range(max_retries):
            try:
                with llm_span(self._settings.openai_model, temperature):
                    response = await self._client.post(
                        url, headers=headers, json=payload,
                        timeout=timeout or self._settings.llm_timeout,
                    )
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as e:
                        status_code = e.response.status_code
                        # Retry on 429 (rate limit) or 5xx (server errors)
                        if status_code == 429 or status_code >= 500:
                            last_exception = e
                            if attempt < max_retries - 1:
                                wait_time = 2 ** attempt  # 1s, 2s, 4s
                                logger.warning(
                                    "LLM request failed with %d, retrying in %ds (attempt %d/%d)",
                                    status_code, wait_time, attempt + 1, max_retries,
                                )
                                await asyncio.sleep(wait_time)
                                continue
                        logger.warning(
                            "LLM request failed: status=%s model=%s base=%s body=%s",
                            status_code,
                            self._settings.openai_model,
                            self._settings.openai_api_base,
                            e.response.text[:500],
                        )
                        _circuit_breaker.record_failure()
                        raise

                # Success
                _circuit_breaker.record_success()
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

            except httpx.HTTPStatusError:
                raise  # Already handled above
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning("LLM request error: %s, retrying in %ds", str(e), wait_time)
                    await asyncio.sleep(wait_time)
                    continue
                _circuit_breaker.record_failure()
                raise

        # All retries exhausted
        _circuit_breaker.record_failure()
        raise last_exception or RuntimeError("LLM request failed after all retries")

    async def astream(
        self,
        prompt: Any,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        response_format: dict | None = None,
        timeout: float | None = None,
        max_retries: int = 3,
    ) -> AsyncIterator[str]:
        """Stream LLM response token by token."""
        if not self.is_enabled:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        if _circuit_breaker.is_open:
            raise RuntimeError("LLM circuit breaker is open, requests temporarily blocked")

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

        last_exception = None
        for attempt in range(max_retries):
            try:
                with llm_span(self._settings.openai_model, temperature):
                    async with self._client.stream(
                        "POST", url, headers=headers, json=payload,
                        timeout=timeout or self._settings.llm_timeout,
                    ) as response:
                        try:
                            response.raise_for_status()
                        except httpx.HTTPStatusError as e:
                            status_code = e.response.status_code
                            # Retry on 429 (rate limit) or 5xx (server errors)
                            if status_code == 429 or status_code >= 500:
                                last_exception = e
                                if attempt < max_retries - 1:
                                    wait_time = 2 ** attempt
                                    logger.warning(
                                        "LLM stream failed with %d, retrying in %ds (attempt %d/%d)",
                                        status_code, wait_time, attempt + 1, max_retries,
                                    )
                                    await asyncio.sleep(wait_time)
                                    continue
                            logger.warning(
                                "LLM stream request failed: status=%s model=%s",
                                status_code, self._settings.openai_model,
                            )
                            _circuit_breaker.record_failure()
                            raise

                        # Success - start yielding tokens
                        _circuit_breaker.record_success()
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
                        return  # Successfully completed

            except httpx.HTTPStatusError:
                raise  # Already handled above
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning("LLM stream error: %s, retrying in %ds", str(e), wait_time)
                    await asyncio.sleep(wait_time)
                    continue
                _circuit_breaker.record_failure()
                raise

        # All retries exhausted
        _circuit_breaker.record_failure()
        raise last_exception or RuntimeError("LLM stream failed after all retries")

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
