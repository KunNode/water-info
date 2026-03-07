"""风险评估工具

供 RiskAssessor 智能体调用，辅助风险等级判定。
"""

from __future__ import annotations

import json
from datetime import datetime

from langchain_core.tools import tool


@tool
def calculate_water_level_risk(
    current_level: float,
    warning_level: float,
    danger_level: float,
    rate_of_change: float = 0.0,
) -> str:
    """根据当前水位计算水位风险分数。

    Args:
        current_level: 当前水位(米)
        warning_level: 警戒水位(米)
        danger_level: 危险水位(米)
        rate_of_change: 水位变化速率(米/时)，正值表示上涨

    Returns:
        JSON格式的风险评估结果
    """
    ratio = 0.0
    if danger_level > warning_level:
        if current_level <= warning_level:
            ratio = current_level / warning_level * 40 if warning_level > 0 else 0
        elif current_level <= danger_level:
            ratio = 40 + (current_level - warning_level) / (danger_level - warning_level) * 40
        else:
            ratio = 80 + min((current_level - danger_level) / danger_level * 100, 20)

    # 水位上涨速率加权
    if rate_of_change > 0:
        ratio = min(ratio + rate_of_change * 10, 100)

    if ratio >= 80:
        level = "critical"
    elif ratio >= 60:
        level = "high"
    elif ratio >= 40:
        level = "moderate"
    elif ratio >= 20:
        level = "low"
    else:
        level = "none"

    return json.dumps({
        "risk_score": round(ratio, 1),
        "risk_level": level,
        "current_level": current_level,
        "warning_level": warning_level,
        "danger_level": danger_level,
        "rate_of_change": rate_of_change,
    }, ensure_ascii=False)


@tool
def calculate_rainfall_risk(
    rainfall_1h: float,
    rainfall_24h: float,
    forecast_24h: float = 0.0,
) -> str:
    """根据降雨量评估降雨风险。

    Args:
        rainfall_1h: 近1小时降雨量(mm)
        rainfall_24h: 近24小时累计降雨量(mm)
        forecast_24h: 未来24小时预报降雨量(mm)

    Returns:
        JSON格式的降雨风险评估
    """
    # 中国气象局暴雨标准: 24h ≥50mm暴雨, ≥100mm大暴雨, ≥250mm特大暴雨
    # 1h ≥16mm短时暴雨
    score = 0.0

    # 1小时降雨评分 (权重40%)
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

    # 24小时降雨评分 (权重40%)
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

    # 预报降雨评分 (权重20%)
    if forecast_24h >= 100:
        sf = 100
    elif forecast_24h >= 50:
        sf = 70
    else:
        sf = forecast_24h / 50 * 40

    score = s1 * 0.4 + s24 * 0.4 + sf * 0.2

    if score >= 80:
        level = "critical"
    elif score >= 60:
        level = "high"
    elif score >= 40:
        level = "moderate"
    elif score >= 20:
        level = "low"
    else:
        level = "none"

    return json.dumps({
        "risk_score": round(score, 1),
        "risk_level": level,
        "rainfall_1h": rainfall_1h,
        "rainfall_24h": rainfall_24h,
        "forecast_24h": forecast_24h,
    }, ensure_ascii=False)


@tool
def calculate_composite_risk(
    water_level_risk_score: float,
    rainfall_risk_score: float,
    active_alarm_count: int = 0,
    upstream_risk_level: str = "none",
) -> str:
    """综合多维度数据计算总体洪水风险。

    Args:
        water_level_risk_score: 水位风险分数 (0-100)
        rainfall_risk_score: 降雨风险分数 (0-100)
        active_alarm_count: 当前活跃告警数量
        upstream_risk_level: 上游风险等级 (none/low/moderate/high/critical)

    Returns:
        JSON格式的综合风险评估
    """
    # 加权综合
    composite = water_level_risk_score * 0.45 + rainfall_risk_score * 0.35

    # 告警数量加权
    alarm_bonus = min(active_alarm_count * 3, 15)
    composite += alarm_bonus

    # 上游风险加权
    upstream_weights = {"none": 0, "low": 2, "moderate": 5, "high": 8, "critical": 12}
    composite += upstream_weights.get(upstream_risk_level, 0)

    composite = min(composite, 100)

    if composite >= 80:
        level = "critical"
        response_level = "I级 (特别重大)"
    elif composite >= 60:
        level = "high"
        response_level = "II级 (重大)"
    elif composite >= 40:
        level = "moderate"
        response_level = "III级 (较大)"
    elif composite >= 20:
        level = "low"
        response_level = "IV级 (一般)"
    else:
        level = "none"
        response_level = "无需响应"

    return json.dumps({
        "composite_risk_score": round(composite, 1),
        "risk_level": level,
        "response_level": response_level,
        "components": {
            "water_level_risk": water_level_risk_score,
            "rainfall_risk": rainfall_risk_score,
            "alarm_bonus": alarm_bonus,
            "upstream_bonus": upstream_weights.get(upstream_risk_level, 0),
        },
        "timestamp": datetime.now().isoformat(),
    }, ensure_ascii=False)


risk_assessment_tools = [
    calculate_water_level_risk,
    calculate_rainfall_risk,
    calculate_composite_risk,
]
