"""Risk assessment tools."""

from __future__ import annotations

import json

from app.risk import (
    calculate_composite_risk as _calculate_composite_risk,
)
from app.risk import (
    calculate_rainfall_risk as _calculate_rainfall_risk,
)
from app.risk import (
    calculate_water_level_risk as _calculate_water_level_risk,
)
from app.tools.simple_tool import SimpleTool


def _water_level(payload: dict) -> str:
    result = _calculate_water_level_risk(
        float(payload.get("current_level", 0)),
        float(payload.get("warning_level", 0)),
        float(payload.get("danger_level", 0)),
        float(payload.get("rate_of_change", 0)),
    )
    return json.dumps(result, ensure_ascii=False)


def _rainfall(payload: dict) -> str:
    result = _calculate_rainfall_risk(
        float(payload.get("rainfall_1h", 0)),
        float(payload.get("rainfall_24h", 0)),
        float(payload.get("forecast_24h", 0)),
    )
    return json.dumps(result, ensure_ascii=False)


def _composite(payload: dict) -> str:
    result = _calculate_composite_risk(
        float(payload.get("water_level_risk_score", 0)),
        float(payload.get("rainfall_risk_score", 0)),
        int(payload.get("active_alarm_count", 0)),
    )
    return json.dumps(result, ensure_ascii=False)


calculate_water_level_risk = SimpleTool("calculate_water_level_risk", _water_level)
calculate_rainfall_risk = SimpleTool("calculate_rainfall_risk", _rainfall)
calculate_composite_risk = SimpleTool("calculate_composite_risk", _composite)

risk_assessment_tools = [
    calculate_water_level_risk,
    calculate_rainfall_risk,
    calculate_composite_risk,
]
