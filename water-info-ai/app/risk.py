"""Deterministic flood risk scoring — no LLM required."""

from __future__ import annotations

from datetime import datetime


def calculate_water_level_risk(
    current_level: float,
    warning_level: float,
    danger_level: float,
    rate_of_change: float = 0.0,
) -> dict:
    """Score water-level risk 0-100 and return a result dict."""
    score = 0.0
    if danger_level > warning_level > 0:
        if current_level <= warning_level:
            score = current_level / warning_level * 40
        elif current_level <= danger_level:
            score = 40 + (current_level - warning_level) / (danger_level - warning_level) * 40
        else:
            score = 80 + min((current_level - danger_level) / danger_level * 100, 20)

    if rate_of_change > 0:
        score = min(score + rate_of_change * 10, 100)

    return {
        "risk_score": round(score, 1),
        "risk_level": _level(score),
        "current_level": current_level,
        "warning_level": warning_level,
        "danger_level": danger_level,
        "rate_of_change": rate_of_change,
    }


def calculate_rainfall_risk(
    rainfall_1h: float,
    rainfall_24h: float,
    forecast_24h: float = 0.0,
) -> dict:
    """Score rainfall risk 0-100 and return a result dict."""
    if rainfall_1h >= 50:
        s1 = 100
    elif rainfall_1h >= 30:
        s1 = 80
    elif rainfall_1h >= 16:
        s1 = 60
    elif rainfall_1h >= 8:
        s1 = 40
    else:
        s1 = rainfall_1h / 8 * 20

    if rainfall_24h >= 250:
        s24 = 100
    elif rainfall_24h >= 100:
        s24 = 80
    elif rainfall_24h >= 50:
        s24 = 60
    elif rainfall_24h >= 25:
        s24 = 40
    else:
        s24 = rainfall_24h / 25 * 20

    if forecast_24h >= 100:
        sf = 100
    elif forecast_24h >= 50:
        sf = 70
    else:
        sf = forecast_24h / 50 * 40

    score = s1 * 0.4 + s24 * 0.4 + sf * 0.2
    return {
        "risk_score": round(score, 1),
        "risk_level": _level(score),
        "rainfall_1h": rainfall_1h,
        "rainfall_24h": rainfall_24h,
        "forecast_24h": forecast_24h,
    }


def calculate_composite_risk(
    water_level_score: float,
    rainfall_score: float,
    active_alarm_count: int = 0,
) -> dict:
    """Combine water-level and rainfall scores into an overall risk assessment."""
    composite = water_level_score * 0.45 + rainfall_score * 0.35
    composite += min(active_alarm_count * 3, 15)
    composite = min(composite, 100)

    level = _level(composite)
    response_levels = {
        "critical": "I级 (特别重大)",
        "high": "II级 (重大)",
        "moderate": "III级 (较大)",
        "low": "IV级 (一般)",
        "none": "无需响应",
    }
    return {
        "composite_risk_score": round(composite, 1),
        "risk_level": level,
        "response_level": response_levels[level],
        "components": {
            "water_level_risk": water_level_score,
            "rainfall_risk": rainfall_score,
            "alarm_bonus": min(active_alarm_count * 3, 15),
        },
        "timestamp": datetime.now().isoformat(),
    }


def _level(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "moderate"
    if score >= 20:
        return "low"
    return "none"
