"""Write compact AI risk assessments back to the platform."""

from __future__ import annotations

from datetime import datetime

from app.services.platform_client import get_platform_client
from app.state import to_plain_data


def _level_value(assessment) -> str:
    if not assessment:
        return "none"
    level = getattr(assessment, "risk_level", None)
    return str(getattr(level, "value", level) or "none")


def _summary_from_state(state: dict) -> str:
    final_response = str(state.get("final_response") or "").strip()
    if final_response:
        return final_response[:2000]
    assessment = state.get("risk_assessment")
    if assessment and getattr(assessment, "key_risks", None):
        return "；".join(assessment.key_risks)[:2000]
    return str(state.get("data_summary") or "AI 巡检已完成")[:2000]


def _plan_excerpt(state: dict) -> str:
    plan = state.get("emergency_plan")
    if not plan:
        return ""
    actions = getattr(plan, "actions", []) or []
    action_text = "；".join(getattr(action, "description", "") for action in actions[:3])
    return (getattr(plan, "summary", "") or action_text or getattr(plan, "plan_name", ""))[:1000]


async def write_assessment(state: dict, *, source: str, station_id: str | None = None, metric_type: str | None = None) -> dict:
    assessment = state.get("risk_assessment")
    affected = getattr(assessment, "affected_stations", []) if assessment else []
    resolved_station_id = station_id or str((affected or [""])[0])
    if not resolved_station_id:
        stations = ((state.get("overview_data") or {}).get("stations") or [])
        resolved_station_id = str(stations[0].get("id", "")) if stations else ""
    if not resolved_station_id:
        raise ValueError("cannot write AI assessment without station id")

    payload = {
        "stationId": resolved_station_id,
        "metricType": metric_type or "",
        "level": _level_value(assessment),
        "summary": _summary_from_state(state),
        "planExcerpt": _plan_excerpt(state),
        "source": source.upper(),
        "assessedAt": datetime.now().isoformat(timespec="seconds"),
        "raw": to_plain_data(state),
    }
    return await get_platform_client().upsert_ai_assessment(payload)
