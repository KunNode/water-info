"""Risk assessor node."""

from __future__ import annotations

import json

from app.risk import calculate_composite_risk, calculate_rainfall_risk, calculate_water_level_risk
from app.services.llm import get_llm
from app.state import RiskAssessment, RiskLevel
from app.state import to_plain_data
from app.utils.json_parser import extract_json


def _to_risk_level(level: str) -> RiskLevel:
    try:
        return RiskLevel(level)
    except Exception:
        return RiskLevel.NONE


def _from_structured_data(state: dict) -> RiskAssessment:
    overview = state.get("overview_data") or {}
    weather = state.get("weather_forecast") or {}
    forecast = weather.get("forecast", weather)
    focus_station = state.get("focus_station")
    stations = [focus_station] if focus_station else overview.get("stations", [])
    alarms = overview.get("active_alarms", [])
    if focus_station:
        alarms = [
            alarm for alarm in alarms
            if str(alarm.get("station_id")) == str(focus_station.get("id"))
        ]
    forecast_24h = float(forecast.get("total_precip_24h_mm", 0))

    max_wl_score = 0.0
    max_rf_score = 0.0
    affected: list[str] = []
    key_risks: list[str] = []

    for station in stations:
        name = station.get("name", station.get("code", "未知站点"))
        wl = station.get("water_level")
        warn = station.get("warning_level")
        danger = station.get("danger_level")
        if wl is not None and warn and danger:
            wl_result = calculate_water_level_risk(float(wl), float(warn), float(danger))
            max_wl_score = max(max_wl_score, wl_result["risk_score"])
            if wl_result["risk_score"] >= 40:
                affected.append(name)
                key_risks.append(f"{name} 水位接近或超过警戒线")

        rainfall = station.get("rainfall")
        if rainfall is not None:
            rf_result = calculate_rainfall_risk(float(rainfall), float(rainfall) * 4, forecast_24h)
            max_rf_score = max(max_rf_score, rf_result["risk_score"])

    if alarms:
        key_risks.append(f"当前存在 {len(alarms)} 条活跃告警")
    if forecast_24h >= 50:
        key_risks.append(f"未来24小时预报降雨量 {forecast_24h:.0f}mm")

    composite = calculate_composite_risk(max_wl_score, max_rf_score, len(alarms))
    return RiskAssessment(
        risk_level=_to_risk_level(composite["risk_level"]),
        risk_score=float(composite["composite_risk_score"]),
        affected_stations=affected,
        key_risks=key_risks or ["当前未发现显著风险"],
        trend="rising" if forecast_24h > 0 else "stable",
        reasoning="基于监测站水位、雨量和活跃告警的综合评分",
        response_level=composite.get("response_level"),
    )


async def risk_assessor_node(state: dict) -> dict:
    assessment = _from_structured_data(state) if state.get("overview_data") else RiskAssessment()
    llm = get_llm()
    station_name = state.get("focus_station", {}).get("name") if state.get("focus_station") else None
    prefix = f"{station_name} 的当前风险判断是" if station_name else "当前整体风险判断是"
    content = f"{prefix} **{assessment.risk_level.value}**，综合评分 {assessment.risk_score:.1f}"

    if llm.is_enabled and state.get("overview_data"):
        try:
            response = await llm.ainvoke(
                json.dumps({
                    "user_query": state.get("user_query", ""),
                    "intent": state.get("intent", "risk_assessment"),
                    "focus_station": to_plain_data(state.get("focus_station")),
                    "overview_data": to_plain_data(state.get("overview_data")),
                    "weather_forecast": to_plain_data(state.get("weather_forecast")),
                    "deterministic_baseline": to_plain_data(assessment),
                }, ensure_ascii=False, indent=2),
                system_prompt=(
                    "你是防汛风险评估智能体。"
                    "如果用户问的是某个具体站点，就优先评估该站点的风险，而不是泛泛地评估全局。"
                    "请结合监测数据和规则基线，输出严格 JSON。"
                    "字段必须包含：risk_level, risk_score, affected_stations, key_risks, trend, reasoning, response_level。"
                    "risk_level 只能是 none/low/moderate/high/critical。"
                ),
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = getattr(response, "content", "") or content
            parsed = extract_json(content) or {}
            if parsed:
                assessment = RiskAssessment(
                    risk_level=_to_risk_level(str(parsed.get("risk_level", assessment.risk_level.value))),
                    risk_score=float(parsed.get("risk_score", assessment.risk_score)),
                    affected_stations=list(parsed.get("affected_stations", assessment.affected_stations)),
                    key_risks=list(parsed.get("key_risks", assessment.key_risks)),
                    trend=parsed.get("trend") or assessment.trend,
                    reasoning=parsed.get("reasoning") or assessment.reasoning,
                    response_level=parsed.get("response_level") or assessment.response_level,
                )
                reasons = "；".join(assessment.key_risks[:2])
                content = f"{prefix} **{assessment.risk_level.value}**，综合评分 {assessment.risk_score:.1f}"
                if reasons:
                    content += f"。主要依据：{reasons}"
        except Exception:
            content = f"{prefix} **{assessment.risk_level.value}**，综合评分 {assessment.risk_score:.1f}"

    return {
        "risk_assessment": assessment,
        "current_agent": "risk_assessor",
        "messages": [{"role": "risk_assessor", "content": content or "风险评估完成"}],
    }
