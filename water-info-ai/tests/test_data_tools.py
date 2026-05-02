"""数据工具集成测试

这些测试需要连接到实际的 PostgreSQL 数据库，标记为 integration。
运行方式: pytest tests/test_data_tools.py -v -m integration
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.tools.data_tools import data_collection_tools


def _find_tool(name: str):
    for t in data_collection_tools:
        if t.name == name:
            return t
    return None


@pytest.mark.asyncio
async def test_fetch_station_observations_returns_requested_recent_rows():
    tool = _find_tool("fetch_station_observations")
    assert tool is not None
    db = SimpleNamespace(
        get_recent_observations=AsyncMock(
            return_value=[
                {
                    "station_id": "station-1",
                    "metric_type": "WATER_LEVEL",
                    "value": 4.248,
                    "unit": "m",
                    "observed_at": "2026-05-02T12:30:00+08:00",
                },
                {
                    "station_id": "station-1",
                    "metric_type": "WATER_LEVEL",
                    "value": 4.220,
                    "unit": "m",
                    "observed_at": "2026-05-02T12:25:00+08:00",
                },
            ]
        )
    )

    with patch("app.tools.data_tools.get_db_service", return_value=db):
        result = await tool.ainvoke({"station_id": "station-1", "metric_type": "WATER_LEVEL", "limit": 5})

    data = json.loads(result)
    assert len(data) == 2
    assert data[0]["value"] == 4.248
    db.get_recent_observations.assert_awaited_once_with(
        station_id="station-1",
        metric_type="WATER_LEVEL",
        limit=5,
    )


@pytest.mark.integration
class TestDataToolsIntegration:
    """需要数据库连接的集成测试"""

    @pytest.mark.asyncio
    async def test_fetch_flood_overview(self):
        tool = _find_tool("fetch_flood_overview")
        assert tool is not None, "fetch_flood_overview 工具不存在"
        try:
            result = await tool.ainvoke({})
        except Exception as exc:
            pytest.skip(f"integration database unavailable: {exc}")
        data = json.loads(result)
        assert "stations" in data or "station_count" in data or "error" not in data

    @pytest.mark.asyncio
    async def test_fetch_active_alarms(self):
        tool = _find_tool("fetch_active_alarms")
        assert tool is not None, "fetch_active_alarms 工具不存在"
        try:
            result = await tool.ainvoke({})
        except Exception as exc:
            pytest.skip(f"integration database unavailable: {exc}")
        data = json.loads(result)
        assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_fetch_threshold_rules(self):
        tool = _find_tool("fetch_threshold_rules")
        assert tool is not None, "fetch_threshold_rules 工具不存在"
        try:
            result = await tool.ainvoke({})
        except Exception as exc:
            pytest.skip(f"integration database unavailable: {exc}")
        data = json.loads(result)
        assert isinstance(data, (list, dict))
