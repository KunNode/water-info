"""Water platform REST API client (Spring Boot)."""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class WaterPlatformClient:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._base_url = self._settings.water_platform_base_url.rstrip("/")
        self._token: str | None = None
        self._client = httpx.AsyncClient(timeout=30.0)

    def _url(self, path: str) -> str:
        return f"{self._base_url}/api/v1{path}"

    async def _ensure_token(self) -> str:
        if self._token:
            return self._token
        resp = await self._client.post(
            self._url("/auth/login"),
            json={
                "username": self._settings.water_platform_username,
                "password": self._settings.water_platform_password,
            },
        )
        resp.raise_for_status()
        self._token = resp.json().get("data", {}).get("accessToken", "")
        return self._token

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._ensure_token()}", "Content-Type": "application/json"}

    async def acknowledge_alarm(self, alarm_id: str) -> dict:
        resp = await self._client.put(self._url(f"/alarms/{alarm_id}/ack"), headers=await self._headers())
        resp.raise_for_status()
        return resp.json()

    async def close_alarm(self, alarm_id: str) -> dict:
        resp = await self._client.post(self._url(f"/alarms/{alarm_id}/close"), headers=await self._headers())
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()


_client: WaterPlatformClient | None = None


def get_platform_client() -> WaterPlatformClient:
    global _client
    if _client is None:
        _client = WaterPlatformClient()
    return _client
