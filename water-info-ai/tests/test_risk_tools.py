"""测试风险评估工具"""

from __future__ import annotations

import json

from app.tools.risk_tools import (
    calculate_composite_risk,
    calculate_rainfall_risk,
    calculate_water_level_risk,
)


class TestWaterLevelRisk:

    def test_below_warning(self):
        result = json.loads(calculate_water_level_risk.invoke({
            "current_level": 10.0,
            "warning_level": 15.0,
            "danger_level": 18.0,
        }))
        assert result["risk_level"] in ("none", "low")
        assert result["risk_score"] < 40

    def test_at_warning(self):
        result = json.loads(calculate_water_level_risk.invoke({
            "current_level": 15.0,
            "warning_level": 15.0,
            "danger_level": 18.0,
        }))
        assert result["risk_level"] == "moderate"

    def test_above_danger(self):
        result = json.loads(calculate_water_level_risk.invoke({
            "current_level": 20.0,
            "warning_level": 15.0,
            "danger_level": 18.0,
        }))
        assert result["risk_level"] in ("critical", "high")
        assert result["risk_score"] >= 80

    def test_rising_rate_increases_risk(self):
        result_stable = json.loads(calculate_water_level_risk.invoke({
            "current_level": 14.0,
            "warning_level": 15.0,
            "danger_level": 18.0,
            "rate_of_change": 0.0,
        }))
        result_rising = json.loads(calculate_water_level_risk.invoke({
            "current_level": 14.0,
            "warning_level": 15.0,
            "danger_level": 18.0,
            "rate_of_change": 2.0,
        }))
        assert result_rising["risk_score"] > result_stable["risk_score"]


class TestRainfallRisk:

    def test_light_rain(self):
        result = json.loads(calculate_rainfall_risk.invoke({
            "rainfall_1h": 2.0,
            "rainfall_24h": 10.0,
        }))
        assert result["risk_level"] in ("none", "low")

    def test_heavy_rain(self):
        result = json.loads(calculate_rainfall_risk.invoke({
            "rainfall_1h": 30.0,
            "rainfall_24h": 120.0,
        }))
        assert result["risk_level"] in ("high", "critical")


class TestCompositeRisk:

    def test_low_composite(self):
        result = json.loads(calculate_composite_risk.invoke({
            "water_level_risk_score": 10.0,
            "rainfall_risk_score": 15.0,
            "active_alarm_count": 0,
        }))
        assert result["risk_level"] in ("none", "low")

    def test_high_composite(self):
        result = json.loads(calculate_composite_risk.invoke({
            "water_level_risk_score": 80.0,
            "rainfall_risk_score": 70.0,
            "active_alarm_count": 5,
            "upstream_risk_level": "high",
        }))
        assert result["risk_level"] in ("high", "critical")
        assert "response_level" in result
