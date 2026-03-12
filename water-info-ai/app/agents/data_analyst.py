"""Data analyst agent."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from loguru import logger

from app.services.llm import get_llm
from app.state import FloodResponseState, StationData
from app.tools.data_tools import data_collection_tools, fetch_flood_overview
from app.tools.weather_tools import fetch_weather_forecast, fetch_weather_warning, weather_tools
from app.utils.timeout import with_timeout

DATA_ANALYST_PROMPT = """你是防汛应急预案系统的数据分析智能体。
你的职责：
1. 收集站点、观测、告警和天气数据
2. 分析当前水情、雨情和设备状态
3. 输出面向后续风险评估的结构化中文摘要
"""


def _to_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_station_data(station: dict[str, Any]) -> StationData:
    return StationData(
        station_id=str(station.get("id", "")),
        station_name=station.get("name", "未知站点"),
        water_level=_to_number(station.get("water_level")),
        water_level_warning=_to_number(station.get("warning_level")),
        water_level_danger=_to_number(station.get("danger_level")),
        rainfall_1h=_to_number(station.get("rainfall")),
        rainfall_24h=_to_number(station.get("rainfall")),
        flow_rate=_to_number(station.get("flow_rate")),
        status=str(station.get("status", "normal")).lower(),
    )


def _station_score(station: dict[str, Any], alarm_counts: Counter[str]) -> float:
    score = 0.0

    water_level = _to_number(station.get("water_level"))
    warning = _to_number(station.get("warning_level"))
    danger = _to_number(station.get("danger_level"))
    rainfall = _to_number(station.get("rainfall"))
    rainfall_warning = _to_number(station.get("rainfall_warning"))
    rainfall_danger = _to_number(station.get("rainfall_danger"))

    if water_level is not None and warning:
        score = max(score, water_level / max(warning, 0.1))
    if water_level is not None and danger:
        score = max(score, 1.2 + water_level / max(danger, 0.1))
    if rainfall is not None and rainfall_warning:
        score = max(score, rainfall / max(rainfall_warning, 0.1))
    if rainfall is not None and rainfall_danger:
        score = max(score, 1.2 + rainfall / max(rainfall_danger, 0.1))

    return score + alarm_counts.get(str(station.get("id", "")), 0)


def _format_station_line(station: dict[str, Any], alarm_counts: Counter[str]) -> str:
    parts: list[str] = [f"- {station.get('name', '未知站点')} ({station.get('code', '-')})"]

    water_level = _to_number(station.get("water_level"))
    warning = _to_number(station.get("warning_level"))
    danger = _to_number(station.get("danger_level"))
    rainfall = _to_number(station.get("rainfall"))
    rainfall_warning = _to_number(station.get("rainfall_warning"))

    if water_level is not None:
        parts.append(f"水位 {water_level:.2f}m")
        if warning is not None:
            parts.append(f"警戒 {warning:.2f}m")
        if danger is not None:
            parts.append(f"危险 {danger:.2f}m")

    if rainfall is not None:
        parts.append(f"降雨 {rainfall:.2f}mm")
        if rainfall_warning is not None:
            parts.append(f"雨量预警 {rainfall_warning:.2f}mm")

    alarm_count = alarm_counts.get(str(station.get("id", "")), 0)
    if alarm_count:
        parts.append(f"关联告警 {alarm_count} 条")

    return "，".join(parts)


def _render_overview_summary(
    overview: dict[str, Any],
    forecast: dict[str, Any],
    weather_warning: dict[str, Any],
) -> str:
    stations = overview.get("stations", [])
    alarms = overview.get("active_alarms", [])
    alarm_counts = Counter(str(alarm.get("station_id", "")) for alarm in alarms)

    sorted_stations = sorted(
        [station for station in stations if isinstance(station, dict)],
        key=lambda station: _station_score(station, alarm_counts),
        reverse=True,
    )
    key_stations = sorted_stations[:5]

    summary_lines = [
        "## 总览",
        f"- 监测站点 {overview.get('station_count', len(stations))} 个",
        f"- 活跃告警 {overview.get('alarm_count', len(alarms))} 条",
    ]

    if key_stations:
        summary_lines.append("")
        summary_lines.append("## 重点站点")
        summary_lines.extend(_format_station_line(station, alarm_counts) for station in key_stations)

    if alarms:
        summary_lines.append("")
        summary_lines.append("## 活跃告警")
        for alarm in alarms[:5]:
            summary_lines.append(
                f"- {alarm.get('station_name', '未知站点')} | {alarm.get('level', '-')}"
                f" | {alarm.get('status', '-')}"
                f" | {alarm.get('message', '无告警详情')}"
            )

    forecast_items = forecast.get("forecast_24h", []) if isinstance(forecast, dict) else []
    total_precip = forecast.get("total_precip_24h_mm") if isinstance(forecast, dict) else None
    if forecast_items or total_precip is not None:
        peak_item = max(
            forecast_items,
            key=lambda item: _to_number(item.get("precip_mm")) or 0.0,
            default=None,
        )
        summary_lines.append("")
        summary_lines.append("## 天气趋势")
        if total_precip is not None:
            summary_lines.append(f"- 未来24小时累计降雨 {total_precip} mm")
        if peak_item:
            summary_lines.append(
                f"- 降雨峰值时段 {peak_item.get('time', '-')}"
                f"，预计 {peak_item.get('precip_mm', 0)} mm"
            )

    warnings = weather_warning.get("warnings", []) if isinstance(weather_warning, dict) else []
    if warnings:
        summary_lines.append("- 气象预警：")
        for warning in warnings[:3]:
            summary_lines.append(f"  - {warning.get('title', warning.get('type', '天气预警'))}")

    return "\n".join(summary_lines)


async def _build_deterministic_bundle() -> dict[str, Any]:
    overview = json.loads(await fetch_flood_overview.ainvoke({}))
    if not isinstance(overview, dict) or overview.get("error"):
        raise RuntimeError(f"failed to fetch overview: {overview}")

    forecast = json.loads(await fetch_weather_forecast.ainvoke({}))
    weather_warning = json.loads(await fetch_weather_warning.ainvoke({}))

    stations = [station for station in overview.get("stations", []) if isinstance(station, dict)]
    alarms = [alarm for alarm in overview.get("active_alarms", []) if isinstance(alarm, dict)]

    return {
        "overview_data": overview,
        "station_data": [_to_station_data(station) for station in stations],
        "alarm_data": alarms,
        "weather_forecast": {
            "forecast": forecast,
            "warning": weather_warning,
        },
        "data_summary": _render_overview_summary(overview, forecast, weather_warning),
    }


async def _build_llm_summary(state: FloodResponseState) -> str:
    llm = get_llm()
    agent = create_react_agent(
        model=llm,
        tools=data_collection_tools + weather_tools,
        prompt=DATA_ANALYST_PROMPT,
    )
    user_query = state.get("user_query", "请分析当前水情数据")
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=f"请根据用户请求进行数据采集与分析：{user_query}")]}
    )
    return result["messages"][-1].content if result["messages"] else ""


@with_timeout(120)
async def data_analyst_node(state: FloodResponseState) -> dict:
    """Collect and summarize flood data for downstream agents."""

    try:
        deterministic = await _build_deterministic_bundle()
        final_message = deterministic["data_summary"]
        logger.info(f"Deterministic data summary generated, length={len(final_message)}")
        return {
            **deterministic,
            "current_agent": "data_analyst",
            "messages": [{"role": "data_analyst", "content": final_message}],
        }
    except Exception as exc:
        logger.warning(f"Deterministic data summary failed, falling back to LLM agent: {exc}")
        final_message = await _build_llm_summary(state)
        logger.info(f"LLM data summary generated, length={len(final_message)}")
        return {
            "data_summary": final_message,
            "current_agent": "data_analyst",
            "messages": [{"role": "data_analyst", "content": final_message}],
        }
