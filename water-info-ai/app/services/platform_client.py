"""Platform client used by execution-related agents."""

from __future__ import annotations

import httpx

from app.config import get_settings


class WaterPlatformClient:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = httpx.AsyncClient(timeout=30.0)
        self._token: str | None = None

    def _build_url(self, path: str) -> str:
        normalized = path if path.startswith("/") else f"/{path}"
        return f"{self._settings.water_platform_base_url.rstrip('/')}/api/v1{normalized}"

    async def _ensure_token(self) -> str:
        if self._token:
            return self._token
        response = await self._client.post(
            self._build_url("/auth/login"),
            json={
                "username": self._settings.water_platform_username,
                "password": self._settings.water_platform_password,
            },
        )
        response.raise_for_status()
        self._token = response.json().get("data", {}).get("accessToken", "")
        return self._token

    async def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {await self._ensure_token()}",
            "Content-Type": "application/json",
        }

    async def acknowledge_alarm(self, alarm_id: str) -> dict:
        response = await self._client.put(self._build_url(f"/alarms/{alarm_id}/ack"), headers=await self._headers())
        response.raise_for_status()
        return response.json()

    async def upsert_ai_assessment(self, payload: dict) -> dict:
        response = await self._client.post(
            self._build_url("/ai-assessments"),
            headers=await self._headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()


_client: WaterPlatformClient | None = None


def get_platform_client() -> WaterPlatformClient:
    global _client
    if _client is None:
        _client = WaterPlatformClient()
    return _client
