"""Risk assessor agent."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from loguru import logger

from app.services.llm import get_llm
from app.state import FloodResponseState, RiskAssessment, RiskLevel
from app.tools.risk_tools import risk_assessment_tools
from app.utils.json_parser import extract_json
from app.utils.timeout import with_timeout

RISK_ASSESSOR_PROMPT = """你是防汛应急预案系统的风险评估智能体。
请基于数据摘要，调用风险计算工具并输出严格 JSON：
{
  "risk_level": "none|low|moderate|high|critical",
  "risk_score": 0-100,
  "affected_stations": ["站点ID"],
  "key_risks": ["关键风险"],
  "trend": "rising|stable|falling",
  "reasoning": "评估说明"
}
"""


def _to_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_to_level(score: float) -> RiskLevel:
    if score >= 80:
        return RiskLevel.CRITICAL
    if score >= 60:
        return RiskLevel.HIGH
    if score >= 40:
        return RiskLevel.MODERATE
    if score >= 20:
        return RiskLevel.LOW
    return RiskLevel.NONE


def _water_score(station: dict[str, Any]) -> tuple[float, str | None]:
    water_level = _to_number(station.get("water_level"))
    warning = _to_number(station.get("warning_level"))
    danger = _to_number(station.get("danger_level"))
    if water_level is None or warning is None or danger is None:
        return 0.0, None

    if water_level >= danger:
        return min(100.0, 80 + (water_level - danger) / max(danger, 0.1) * 20), "水位超过危险线"
    if water_level >= warning:
        return 40 + (water_level - warning) / max(danger - warning, 0.1) * 40, "水位超过警戒线"

    score = water_level / max(warning, 0.1) * 40
    note = "水位接近警戒线" if score >= 25 else None
    return score, note


def _rain_score(station: dict[str, Any], forecast_total: float) -> tuple[float, str | None]:
    rainfall = _to_number(station.get("rainfall"))
    warning = _to_number(station.get("rainfall_warning"))
    danger = _to_number(station.get("rainfall_danger"))
    if rainfall is None:
        base = 0.0
    elif danger is not None and rainfall >= danger:
        base = 85.0
    elif warning is not None and rainfall >= warning:
        base = 55.0
    elif warning:
        base = rainfall / max(warning, 0.1) * 35
    else:
        base = min(rainfall, 20.0)

    forecast_bonus = min(forecast_total / 5, 20.0)
    score = min(100.0, base + forecast_bonus)

    if score >= 80:
        return score, "强降雨风险高"
    if score >= 40:
        return score, "降雨可能持续推高风险"
    return score, None


def _build_deterministic_risk(state: FloodResponseState) -> RiskAssessment | None:
    overview = state.get("overview_data")
    if not overview:
        return None

    stations = [station for station in overview.get("stations", []) if isinstance(station, dict)]
    alarms = [alarm for alarm in overview.get("active_alarms", []) if isinstance(alarm, dict)]
    weather = state.get("weather_forecast", {})
    forecast = weather.get("forecast", {}) if isinstance(weather, dict) else {}
    forecast_total = _to_number(forecast.get("total_precip_24h_mm")) or 0.0

    top_water_score = 0.0
    top_rain_score = 0.0
    affected_stations: list[str] = []
    key_risks: list[str] = []

    for station in stations:
        station_id = station.get("code") or station.get("id") or station.get("name", "")
        water_score, water_note = _water_score(station)
        rain_score, rain_note = _rain_score(station, forecast_total)
        station_score = max(water_score, rain_score)

        top_water_score = max(top_water_score, water_score)
        top_rain_score = max(top_rain_score, rain_score)

        if station_score >= 40:
            affected_stations.append(str(station_id))
        if water_note:
            key_risks.append(f"{station.get('name', '未知站点')}{water_note}")
        if rain_note and station_score >= 40:
            key_risks.append(f"{station.get('name', '未知站点')}{rain_note}")

    for alarm in alarms[:5]:
        station_name = alarm.get("station_name", "未知站点")
        key_risks.append(f"{station_name}{alarm.get('message', '存在活跃告警')}")
        station_id = alarm.get("station_id")
        if station_id:
            affected_stations.append(str(station_id))

    alarm_bonus = min(len(alarms) * 5, 20)
    total_score = min(100.0, top_water_score * 0.5 + top_rain_score * 0.35 + alarm_bonus)
    if forecast_total >= 50:
        total_score = min(100.0, total_score + 8)
    if forecast_total >= 100:
        total_score = min(100.0, total_score + 6)

    risk_level = _score_to_level(total_score)
    trend = "rising" if forecast_total >= 50 or len(alarms) >= 2 else "stable"

    reasoning = (
        f"最高水位风险分 {top_water_score:.1f}，最高雨量风险分 {top_rain_score:.1f}，"
        f"活跃告警 {len(alarms)} 条，未来24小时降雨 {forecast_total:.1f} mm。"
    )

    return RiskAssessment(
        risk_level=risk_level,
        risk_score=round(total_score, 1),
        affected_stations=sorted(set(affected_stations)),
        key_risks=key_risks[:5],
        trend=trend,
        reasoning=reasoning,
    )


async def _build_llm_risk(state: FloodResponseState) -> tuple[RiskAssessment, str]:
    llm = get_llm()
    agent = create_react_agent(
        model=llm,
        tools=risk_assessment_tools,
        prompt=RISK_ASSESSOR_PROMPT,
    )
    data_summary = state.get("data_summary", "暂无数据分析结果")
    prompt = f"""请基于以下数据分析结果进行风险评估：

{data_summary}

请使用工具进行量化计算，并输出综合风险评估结果。
"""
    result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
    final_message = result["messages"][-1].content if result["messages"] else ""
    risk_data = extract_json(final_message)
    if risk_data and isinstance(risk_data, dict):
        try:
            assessment = RiskAssessment(
                risk_level=RiskLevel(risk_data.get("risk_level", "none")),
                risk_score=float(risk_data.get("risk_score", 0)),
                affected_stations=risk_data.get("affected_stations", []),
                key_risks=risk_data.get("key_risks", []),
                trend=risk_data.get("trend", "stable"),
                reasoning=risk_data.get("reasoning", final_message),
            )
            return assessment, final_message
        except (ValueError, KeyError):
            pass
    return RiskAssessment(reasoning=final_message), final_message


@with_timeout(120)
async def risk_assessor_node(state: FloodResponseState) -> dict:
    deterministic = _build_deterministic_risk(state)
    if deterministic is not None:
        logger.info(
            f"Deterministic risk assessment generated: level={deterministic.risk_level.value}, score={deterministic.risk_score}"
        )
        return {
            "risk_assessment": deterministic,
            "current_agent": "risk_assessor",
            "messages": [{"role": "risk_assessor", "content": json.dumps(deterministic.model_dump(), ensure_ascii=False)}],
        }

    risk_assessment, final_message = await _build_llm_risk(state)
    logger.info(f"LLM risk assessment generated: {final_message[:200]}")
    return {
        "risk_assessment": risk_assessment,
        "current_agent": "risk_assessor",
        "messages": [{"role": "risk_assessor", "content": final_message}],
    }
