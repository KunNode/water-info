"""数据工具集成测试

这些测试需要连接到实际的 PostgreSQL 数据库，标记为 integration。
运行方式: pytest tests/test_data_tools.py -v -m integration
"""

from __future__ import annotations

import json

import pytest

from app.tools.data_tools import data_collection_tools


def _find_tool(name: str):
    for t in data_collection_tools:
        if t.name == name:
            return t
    return None


@pytest.mark.integration
class TestDataToolsIntegration:
    """需要数据库连接的集成测试"""

    @pytest.mark.asyncio
    async def test_fetch_flood_overview(self):
        tool = _find_tool("fetch_flood_overview")
        assert tool is not None, "fetch_flood_overview 工具不存在"
        result = await tool.ainvoke({})
        data = json.loads(result)
        assert "stations" in data or "station_count" in data or "error" not in data

    @pytest.mark.asyncio
    async def test_fetch_active_alarms(self):
        tool = _find_tool("fetch_active_alarms")
        assert tool is not None, "fetch_active_alarms 工具不存在"
        result = await tool.ainvoke({})
        data = json.loads(result)
        assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_fetch_threshold_rules(self):
        tool = _find_tool("fetch_threshold_rules")
        assert tool is not None, "fetch_threshold_rules 工具不存在"
        result = await tool.ainvoke({})
        data = json.loads(result)
        assert isinstance(data, (list, dict))
