"""Deterministic risk scoring helpers."""

from __future__ import annotations


def _level_for_score(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "moderate"
    if score >= 20:
        return "low"
    return "none"


def _response_for_level(level: str) -> str:
    return {
        "critical": "I级响应",
        "high": "II级响应",
        "moderate": "III级响应",
        "low": "IV级响应",
        "none": "常态监测",
    }.get(level, "IV级响应")


def calculate_water_level_risk(
    current_level: float,
    warning_level: float,
    danger_level: float,
    rate_of_change: float = 0.0,
) -> dict:
    if warning_level <= 0 or danger_level <= warning_level:
        score = 0.0
    elif current_level >= danger_level:
        score = 80.0 + min(20.0, (current_level - danger_level) * 10.0)
    elif current_level >= warning_level:
        span = danger_level - warning_level
        score = 40.0 + ((current_level - warning_level) / span) * 40.0
    else:
        margin = max(warning_level - current_level, 0.0)
        score = max(0.0, 35.0 - margin * 7.0)

    if rate_of_change > 0:
        score += min(20.0, rate_of_change * 5.0)

    score = round(max(0.0, min(100.0, score)), 1)
    level = _level_for_score(score)
    return {
        "risk_level": level,
        "risk_score": score,
        "response_level": _response_for_level(level),
        "factors": {
            "current_level": current_level,
            "warning_level": warning_level,
            "danger_level": danger_level,
            "rate_of_change": rate_of_change,
        },
    }


def calculate_rainfall_risk(
    rainfall_1h: float,
    rainfall_24h: float,
    forecast_24h: float = 0.0,
) -> dict:
    score = 0.0
    score = max(score, min(55.0, rainfall_1h / 30.0 * 55.0))
    score = max(score, min(70.0, rainfall_24h / 100.0 * 70.0))
    score += min(30.0, forecast_24h / 100.0 * 30.0)
    score = round(max(0.0, min(100.0, score)), 1)
    level = _level_for_score(score)
    return {
        "risk_level": level,
        "risk_score": score,
        "response_level": _response_for_level(level),
        "factors": {
            "rainfall_1h": rainfall_1h,
            "rainfall_24h": rainfall_24h,
            "forecast_24h": forecast_24h,
        },
    }


def calculate_composite_risk(
    water_level_risk_score: float,
    rainfall_risk_score: float,
    active_alarm_count: int = 0,
) -> dict:
    alarm_score = min(100.0, active_alarm_count * 15.0)
    score = (
        max(0.0, water_level_risk_score) * 0.45
        + max(0.0, rainfall_risk_score) * 0.35
        + alarm_score * 0.20
    )
    score = round(max(0.0, min(100.0, score)), 1)
    level = _level_for_score(score)
    return {
        "risk_level": level,
        "composite_risk_score": score,
        "risk_score": score,
        "response_level": _response_for_level(level),
        "components": {
            "water_level_risk_score": water_level_risk_score,
            "rainfall_risk_score": rainfall_risk_score,
            "active_alarm_count": active_alarm_count,
            "alarm_score": alarm_score,
        },
    }
