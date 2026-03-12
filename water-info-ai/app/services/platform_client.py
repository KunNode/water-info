"""水务平台 API 客户端

封装对现有 Spring Boot 后端的 HTTP 调用，供智能体工具使用。
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.config import get_settings


class WaterPlatformClient:
    """水务平台 REST API 客户端"""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._base_url = self._settings.water_platform_base_url.rstrip("/")
        self._api_prefix = "/api/v1"
        self._token: str | None = None
        self._client = httpx.AsyncClient(timeout=30.0)

    def _build_url(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{self._base_url}{self._api_prefix}{normalized_path}"

    async def _ensure_token(self) -> str:
        """确保持有有效 JWT token"""
        if self._token:
            return self._token
        resp = await self._client.post(
            self._build_url("/auth/login"),
            json={
                "username": self._settings.water_platform_username,
                "password": self._settings.water_platform_password,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data.get("data", {}).get("accessToken", "")
        logger.info("水务平台登录成功")
        return self._token

    async def _headers(self) -> dict[str, str]:
        token = await self._ensure_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def _get(self, path: str, params: dict | None = None) -> dict:
        headers = await self._headers()
        resp = await self._client.get(self._build_url(path), headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json_data: dict | None = None) -> dict:
        headers = await self._headers()
        resp = await self._client.post(self._build_url(path), headers=headers, json=json_data)
        resp.raise_for_status()
        return resp.json()

    async def _put(self, path: str, json_data: dict | None = None) -> dict:
        headers = await self._headers()
        resp = await self._client.put(self._build_url(path), headers=headers, json=json_data)
        resp.raise_for_status()
        return resp.json()

    # ──────────────────────────────────────
    # 监测站
    # ──────────────────────────────────────

    async def get_stations(self, page: int = 1, size: int = 100) -> dict:
        """获取监测站列表"""
        return await self._get("/stations", params={"page": page, "size": size})

    async def get_station(self, station_id: str) -> dict:
        """获取单个监测站详情"""
        return await self._get(f"/stations/{station_id}")

    # ──────────────────────────────────────
    # 传感器
    # ──────────────────────────────────────

    async def get_sensors(self, station_id: str | None = None, page: int = 1, size: int = 100) -> dict:
        """获取传感器列表"""
        params: dict = {"page": page, "size": size}
        if station_id:
            params["stationId"] = station_id
        return await self._get("/sensors", params=params)

    # ──────────────────────────────────────
    # 观测数据
    # ──────────────────────────────────────

    async def get_observations(
        self,
        station_id: str | None = None,
        metric_type: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        page: int = 1,
        size: int = 200,
    ) -> dict:
        """获取观测数据"""
        params: dict = {"page": page, "size": size}
        if station_id:
            params["stationId"] = station_id
        if metric_type:
            params["metricType"] = metric_type
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return await self._get("/observations", params=params)

    # ──────────────────────────────────────
    # 告警
    # ──────────────────────────────────────

    async def get_alarms(
        self,
        station_id: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 100,
    ) -> dict:
        """获取告警列表"""
        params: dict = {"page": page, "size": size}
        if station_id:
            params["stationId"] = station_id
        if status:
            params["status"] = status
        return await self._get("/alarms", params=params)

    async def acknowledge_alarm(self, alarm_id: str) -> dict:
        """确认告警"""
        return await self._put(f"/alarms/{alarm_id}/ack")

    async def close_alarm(self, alarm_id: str) -> dict:
        """关闭告警"""
        return await self._post(f"/alarms/{alarm_id}/close")

    # ──────────────────────────────────────
    # 阈值规则
    # ──────────────────────────────────────

    async def get_threshold_rules(
        self,
        station_id: str | None = None,
        metric_type: str | None = None,
        enabled: bool | None = None,
        page: int = 1,
        size: int = 100,
    ) -> dict:
        """获取阈值规则"""
        params: dict = {"page": page, "size": size}
        if station_id:
            params["stationId"] = station_id
        if metric_type:
            params["metricType"] = metric_type
        if enabled is not None:
            params["enabled"] = str(enabled).lower()
        return await self._get("/threshold-rules", params=params)

    # ──────────────────────────────────────
    # 资源清理
    # ──────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()


# 全局单例
_client: WaterPlatformClient | None = None


def get_platform_client() -> WaterPlatformClient:
    global _client
    if _client is None:
        _client = WaterPlatformClient()
    return _client
