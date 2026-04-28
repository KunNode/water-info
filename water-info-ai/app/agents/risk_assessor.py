"""Risk assessor node."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.rag.service import format_evidence_markdown
from app.risk import calculate_composite_risk, calculate_rainfall_risk, calculate_water_level_risk
from app.services.llm import get_llm
from app.state import RiskAssessment, RiskLevel, to_plain_data
from app.utils.json_parser import extract_json


class RiskAssessmentPayload(BaseModel):
    risk_level: str
    risk_score: float = Field(ge=0, le=100)
    affected_stations: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    trend: str | None = None
    reasoning: str | None = None
    response_level: str | None = None


RISK_ORDER = {
    RiskLevel.NONE: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MODERATE: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}


def _to_risk_level(level: str) -> RiskLevel:
    try:
        return RiskLevel(level)
    except Exception:
        return RiskLevel.NONE


def _level_for_score(score: float) -> RiskLevel:
    if score >= 80:
        return RiskLevel.CRITICAL
    if score >= 60:
        return RiskLevel.HIGH
    if score >= 40:
        return RiskLevel.MODERATE
    if score >= 20:
        return RiskLevel.LOW
    return RiskLevel.NONE


def _max_level(left: RiskLevel, right: RiskLevel) -> RiskLevel:
    return left if RISK_ORDER[left] >= RISK_ORDER[right] else right


def _format_assessment_content(assessment: RiskAssessment, prefix: str) -> str:
    content = f"{prefix} **{assessment.risk_level.value}**，综合评分 {assessment.risk_score:.1f}"
    reasons = "；".join(assessment.key_risks[:2])
    if reasons:
        content += f"。主要依据：{reasons}"
    return content


def _assessment_from_model(parsed: dict, baseline: RiskAssessment) -> RiskAssessment:
    payload = RiskAssessmentPayload.model_validate(parsed)
    score = float(payload.risk_score)
    level = _to_risk_level(payload.risk_level)
    key_risks = list(payload.key_risks) or list(baseline.key_risks)

    if baseline.risk_score > 0:
        conservative_floor = max(0.0, baseline.risk_score - 15.0)
        if score < conservative_floor:
            score = conservative_floor
            key_risks.append("模型风险分低于监测规则基线，已按阈值结果保守上调")
        level = _max_level(level, _level_for_score(score))

    return RiskAssessment(
        risk_level=level,
        risk_score=round(score, 1),
        affected_stations=list(payload.affected_stations) or list(baseline.affected_stations),
        key_risks=key_risks or ["当前未发现显著风险"],
        trend=payload.trend or baseline.trend,
        reasoning=payload.reasoning or baseline.reasoning,
        response_level=payload.response_level or baseline.response_level,
    )


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
    evidence = list(state.get("evidence_context") or [])
    llm = get_llm()
    station_name = state.get("focus_station", {}).get("name") if state.get("focus_station") else None
    prefix = f"{station_name} 的当前风险判断是" if station_name else "当前整体风险判断是"
    content = _format_assessment_content(assessment, prefix)

    if llm.is_enabled and state.get("overview_data"):
        try:
            response = await llm.ainvoke(
                json.dumps({
                    "user_query": state.get("user_query", ""),
                    "intent": state.get("intent", "risk_assessment"),
                    "focus_station": to_plain_data(state.get("focus_station")),
                    "overview_data": to_plain_data(state.get("overview_data")),
                    "weather_forecast": to_plain_data(state.get("weather_forecast")),
                    "evidence": to_plain_data(evidence),
                    "deterministic_baseline": to_plain_data(assessment),
                }, ensure_ascii=False, indent=2),
                system_prompt=(
                    "你是防汛风险评估智能体。"
                    "如果用户问的是某个具体站点，就优先评估该站点的风险，而不是泛泛地评估全局。"
                    "如果 evidence 非空，请把可引用的专业依据融入 reasoning，并保留 [1][2] 编号。"
                    "如果 evidence 为空，不要编造制度或规范。"
                    "请结合监测数据和规则基线，输出严格 JSON。"
                    "字段必须包含：risk_level, risk_score, affected_stations, key_risks, "
                    "trend, reasoning, response_level。"
                    "risk_level 只能是 none/low/moderate/high/critical。"
                ),
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            parsed = extract_json(getattr(response, "content", None)) or {}
            if parsed:
                assessment = _assessment_from_model(parsed, assessment)
                content = _format_assessment_content(assessment, prefix)
        except Exception:
            content = _format_assessment_content(assessment, prefix)

    if evidence:
        content = f"{content}\n\n{format_evidence_markdown(evidence)}"

    return {
        "risk_assessment": assessment,
        "current_agent": "risk_assessor",
        "messages": [{"role": "risk_assessor", "content": content or "风险评估完成"}],
    }
