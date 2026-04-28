"""Embedding client for the knowledge base."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import get_settings


class EmbeddingClient:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = httpx.AsyncClient(timeout=self._settings.llm_timeout)

    @property
    def is_enabled(self) -> bool:
        return bool(self._settings.embedding_api_base and self._settings.embedding_model)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def embed_texts(self, texts: list[str], *, batch_size: int = 16) -> list[list[float]]:
        if not texts:
            return []
        if not self.is_enabled:
            raise RuntimeError("Embedding API is not configured")

        all_vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            all_vectors.extend(await self._embed_batch(batch))
        return all_vectors

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        headers = {"Content-Type": "application/json"}
        if self._settings.embedding_api_key:
            headers["Authorization"] = f"Bearer {self._settings.embedding_api_key}"

        payload: dict[str, Any] = {
            "model": self._settings.embedding_model,
            "input": texts,
        }
        url = f"{self._settings.embedding_api_base.rstrip('/')}/embeddings"

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await self._client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                items = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
                return [list(item.get("embedding", [])) for item in items]
            except Exception as exc:  # pragma: no cover - network failure path
                last_error = exc
                await asyncio.sleep(0.5 * (2**attempt))
        raise RuntimeError(f"Embedding request failed: {last_error}") from last_error


_embedding_client: EmbeddingClient | None = None


def get_embedding_client() -> EmbeddingClient:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client
