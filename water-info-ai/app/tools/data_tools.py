"""Data collection tools for water situation retrieval."""

from __future__ import annotations

import json

from app.database import get_db_service
from app.tools.simple_tool import SimpleTool


async def _fetch_flood_overview(_: dict) -> str:
    data = await get_db_service().get_flood_situation_overview()
    return json.dumps(data, ensure_ascii=False)


async def _fetch_station_observations(payload: dict) -> str:
    station_id = payload.get("station_id")
    if station_id:
        data = await get_db_service().get_rainfall_stats(station_id)
    else:
        data = await get_db_service().get_station_with_latest_data()
    return json.dumps(data, ensure_ascii=False)


async def _fetch_active_alarms(payload: dict) -> str:
    data = await get_db_service().get_active_alarms(payload.get("station_id"))
    return json.dumps(data, ensure_ascii=False)


async def _fetch_threshold_rules(_: dict) -> str:
    data = await get_db_service().get_station_thresholds_summary()
    return json.dumps(data, ensure_ascii=False)


data_collection_tools = [
    SimpleTool("fetch_flood_overview", _fetch_flood_overview),
    SimpleTool("fetch_station_observations", _fetch_station_observations),
    SimpleTool("fetch_active_alarms", _fetch_active_alarms),
    SimpleTool("fetch_threshold_rules", _fetch_threshold_rules),
]
