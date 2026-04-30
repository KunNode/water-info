"""Policy for deciding whether generated emergency plans are persisted."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.state import RiskLevel

SOURCE_MANUAL = "manual"
SOURCE_EVENT = "event"
EVENT_PERSIST_LEVELS = {RiskLevel.MODERATE.value, RiskLevel.HIGH.value, RiskLevel.CRITICAL.value}
MANUAL_PLAN_KEYWORDS = ("预案", "方案", "响应", "处置方案", "保存预案", "写入预案", "生成")


@dataclass(frozen=True)
class PlanPersistenceDecision:
    should_persist: bool
    source: str
    mode: str
    reason: str
    plan_id: str | None = None


def should_persist_plan(state: dict, *, source: str) -> PlanPersistenceDecision:
    if not state.get("emergency_plan"):
        return PlanPersistenceDecision(False, source, "skip", "no emergency plan in state")
    if source == SOURCE_EVENT:
        return _event_decision(state)
    return _manual_decision(state)


def _manual_decision(state: dict) -> PlanPersistenceDecision:
    if not _manual_plan_requested(state):
        return PlanPersistenceDecision(
            False,
            SOURCE_MANUAL,
            "skip",
            "manual request did not ask for a plan",
        )
    return PlanPersistenceDecision(True, SOURCE_MANUAL, "create", "manual plan request")


def _event_decision(state: dict) -> PlanPersistenceDecision:
    level = _risk_level_value(state)
    if level not in EVENT_PERSIST_LEVELS:
        return PlanPersistenceDecision(
            False,
            SOURCE_EVENT,
            "skip",
            f"risk level {level} is below event persistence threshold",
        )
    if not _has_concrete_event_evidence(state):
        return PlanPersistenceDecision(
            False,
            SOURCE_EVENT,
            "skip",
            "event persistence requires concrete evidence",
        )
    return PlanPersistenceDecision(True, SOURCE_EVENT, "create", "event risk threshold met")


def _manual_plan_requested(state: dict) -> bool:
    intent = str(state.get("intent") or "")
    query = str(state.get("user_query") or "")
    if intent in {"plan_generation", "resource_dispatch", "notification"}:
        return True
    return any(keyword in query for keyword in MANUAL_PLAN_KEYWORDS)


def _risk_level_value(state: dict) -> str:
    assessment = state.get("risk_assessment")
    if not assessment:
        return RiskLevel.NONE.value
    level = getattr(assessment, "risk_level", RiskLevel.NONE)
    return str(getattr(level, "value", level) or RiskLevel.NONE.value)


def _risk_score(state: dict) -> float:
    assessment = state.get("risk_assessment")
    return float(getattr(assessment, "risk_score", 0.0) or 0.0) if assessment else 0.0


def _response_level(state: dict) -> str:
    assessment = state.get("risk_assessment")
    return str(getattr(assessment, "response_level", "") or "") if assessment else ""


def _key_risks(state: dict) -> list[str]:
    assessment = state.get("risk_assessment")
    return [str(item) for item in (getattr(assessment, "key_risks", []) or [])] if assessment else []


def _affected_stations(state: dict) -> list[str]:
    assessment = state.get("risk_assessment")
    return [str(item) for item in (getattr(assessment, "affected_stations", []) or [])] if assessment else []


def _active_alarms(state: dict) -> list[dict]:
    return list((state.get("overview_data") or {}).get("active_alarms") or [])


def _stations(state: dict) -> list[dict]:
    return list((state.get("overview_data") or {}).get("stations") or [])


def _evidence_context(state: dict) -> list[Any]:
    return list(state.get("evidence_context") or state.get("evidence") or [])


def _has_concrete_event_evidence(state: dict) -> bool:
    if str(state.get("focus_station_query") or "").strip():
        return True
    if _active_alarms(state):
        return True
    if _stations(state):
        return True
    if _evidence_context(state):
        return True
    if _affected_stations(state):
        return True
    return bool(_key_risks(state))


def build_trigger_conditions(state: dict, *, source: str) -> str:
    level = _risk_level_value(state)
    score = _risk_score(state)
    response_level = _response_level(state)
    source_label = "自动事件触发" if source == SOURCE_EVENT else "人工对话请求"

    if source == SOURCE_MANUAL and level in {RiskLevel.NONE.value, RiskLevel.LOW.value}:
        summary = (
            f"摘要：人工请求生成防汛应急预案；当前综合风险为 {level}，"
            "未达到自动事件入库门槛，本预案作为人工草案保存。"
        )
    else:
        summary = _summary_line(state, source_label, level, response_level)

    lines = [
        summary,
        "",
        "关键依据：",
        f"1. 风险等级：{level}，综合评分 {score:.1f}" + (f"，响应等级 {response_level}。" if response_level else "。"),
    ]
    index = 2

    station_line = _station_line(state)
    if station_line:
        lines.append(f"{index}. {station_line}")
        index += 1

    alarm_line = _alarm_line(state)
    if alarm_line:
        lines.append(f"{index}. {alarm_line}")
        index += 1

    evidence_line = _evidence_line(state)
    if evidence_line:
        lines.append(f"{index}. {evidence_line}")
        index += 1

    if source == SOURCE_MANUAL and level in {RiskLevel.NONE.value, RiskLevel.LOW.value}:
        lines.append(f"{index}. 自动入库判断：未满足 moderate/high/critical 自动事件触发条件。")
        index += 1

    focus = str(state.get("focus_station_query") or "").strip()
    metric = _metric_type(state)
    suffix = f"，station={focus}" if focus else ""
    suffix += f"，metric={metric}" if metric else ""
    lines.append(f"{index}. 来源：{source_label}{suffix}。")

    return "\n".join(lines)[:1200]


def _summary_line(state: dict, source_label: str, level: str, response_level: str) -> str:
    risks = _key_risks(state)
    first_risk = risks[0] if risks else "当前防汛态势达到预案生成条件"
    response = f"，触发 {response_level} 预案" if response_level else "，触发应急预案"
    return f"摘要：{first_risk}{response}。来源：{source_label}，风险等级 {level}。"


def _station_line(state: dict) -> str:
    stations = _stations(state)
    if not stations:
        affected = _affected_stations(state)
        return f"站点指标：影响站点 {', '.join(affected)}。" if affected else ""
    station = stations[0]
    name = station.get("name") or station.get("code") or station.get("id") or "未知站点"
    if station.get("water_level") is not None:
        return (
            f"站点指标：{name} WATER_LEVEL 当前值 {station.get('water_level')}m，"
            f"警戒线 {station.get('warning_level', '未配置')}m，危险线 {station.get('danger_level', '未配置')}m。"
        )
    metric = station.get("metric_type") or "UNKNOWN"
    value = station.get("value") or station.get("latest_value") or "未提供"
    return f"站点指标：{name} {metric} 当前值 {value}。"


def _alarm_line(state: dict) -> str:
    alarms = _active_alarms(state)
    if not alarms:
        return ""
    highest = _highest_alarm_level(alarms)
    active_statuses = sorted({str(alarm.get("status", "OPEN")) for alarm in alarms})
    return f"告警事件：当前存在 {len(alarms)} 条 {'/'.join(active_statuses)} 告警，最高等级 {highest}。"


def _highest_alarm_level(alarms: list[dict]) -> str:
    order = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}
    levels = [str(alarm.get("level", "INFO")).upper() for alarm in alarms]
    return max(levels, key=lambda level: order.get(level, -1)) if levels else "INFO"


def _evidence_line(state: dict) -> str:
    evidence = _evidence_context(state)
    if not evidence:
        return ""
    parts = []
    for item in evidence[:3]:
        if isinstance(item, dict):
            citation_id = str(item.get("citation_id", "")).strip()
            title = str(item.get("document_title", "")).strip()
        else:
            citation_id = str(getattr(item, "citation_id", "")).strip()
            title = str(getattr(item, "document_title", "")).strip()
        if citation_id and title:
            parts.append(f"{citation_id}《{title}》")
    return f"业务依据：{'；'.join(parts)}。" if parts else ""


def _metric_type(state: dict) -> str:
    alarms = _active_alarms(state)
    if alarms and alarms[0].get("metric_type"):
        return str(alarms[0]["metric_type"])
    stations = _stations(state)
    if stations and stations[0].get("metric_type"):
        return str(stations[0]["metric_type"])
    return ""


def build_event_session_id(station_id: str, metric_type: str, window: str | None = None) -> str:
    resolved_window = window or datetime.now().strftime("%Y%m%d%H%M")
    return f"risk-event:{station_id}:{metric_type}:{resolved_window}"


def event_window(iso_timestamp: str | None = None) -> str:
    if iso_timestamp:
        parsed = datetime.fromisoformat(iso_timestamp)
    else:
        parsed = datetime.now()
    minute = 0 if parsed.minute < 30 else 30
    return parsed.replace(minute=minute, second=0, microsecond=0).strftime("%Y%m%d%H%M")
