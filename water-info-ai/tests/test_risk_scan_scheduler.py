from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.risk_scan_scheduler import RiskScanScheduler
from app.state import EmergencyAction, EmergencyPlan, RiskAssessment, RiskLevel


@pytest.mark.asyncio
async def test_event_scan_persists_moderate_plan_with_event_session(monkeypatch):
    scheduler = RiskScanScheduler()
    plan = EmergencyPlan(
        plan_id="EP-EVENT-001",
        plan_name="翠屏湖事件预案",
        actions=[
            EmergencyAction(
                action_id="A-001",
                action_type="monitoring",
                description="加密监测",
                responsible_dept="监测调度科",
            )
        ],
    )
    graph_state = {
        "user_query": "事件巡检",
        "focus_station_query": "ST_CP_LAKE_01",
        "risk_assessment": RiskAssessment(
            risk_level=RiskLevel.MODERATE,
            risk_score=55.0,
            key_risks=["翠屏湖心水位超过警戒线"],
            response_level="III级响应",
        ),
        "overview_data": {
            "active_alarms": [{"level": "WARNING", "status": "OPEN", "metric_type": "WATER_LEVEL"}],
            "stations": [{"id": "ST_CP_LAKE_01", "name": "翠屏湖心水位站", "water_level": 3.9}],
        },
        "emergency_plan": plan,
        "resource_plan": [],
        "notifications": [],
    }
    db = SimpleNamespace(
        find_recent_event_plan=AsyncMock(return_value=None),
        save_emergency_plan=AsyncMock(),
        save_resource_allocations=AsyncMock(),
        save_notifications=AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.risk_scan_scheduler.risk_event_graph",
        SimpleNamespace(ainvoke=AsyncMock(return_value=graph_state)),
    )
    monkeypatch.setattr("app.services.risk_scan_scheduler.write_assessment", AsyncMock(return_value={"code": 200}))
    monkeypatch.setattr("app.services.risk_scan_scheduler.get_db_service", lambda: db)
    monkeypatch.setattr("app.services.risk_scan_scheduler.event_window", lambda: "202604301000")

    await scheduler._event_scan("ST_CP_LAKE_01", "WATER_LEVEL", "WARNING")

    db.save_emergency_plan.assert_awaited_once()
    saved_kwargs = db.save_emergency_plan.await_args.kwargs
    assert saved_kwargs["plan_id"] == "EP-EVENT-001"
    assert saved_kwargs["session_id"] == "risk-event:ST_CP_LAKE_01:WATER_LEVEL:202604301000"
    assert "来源：自动事件触发" in saved_kwargs["trigger_conditions"]


@pytest.mark.asyncio
async def test_event_scan_skips_low_risk_plan_persistence(monkeypatch):
    scheduler = RiskScanScheduler()
    graph_state = {
        "focus_station_query": "ST_CP_LAKE_01",
        "risk_assessment": RiskAssessment(risk_level=RiskLevel.LOW, risk_score=18.0),
        "overview_data": {"active_alarms": [], "stations": [{"id": "ST_CP_LAKE_01"}]},
        "emergency_plan": EmergencyPlan(plan_id="EP-LOW", plan_name="低风险事件预案"),
    }
    db = SimpleNamespace(
        find_recent_event_plan=AsyncMock(return_value=None),
        save_emergency_plan=AsyncMock(),
        save_resource_allocations=AsyncMock(),
        save_notifications=AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.risk_scan_scheduler.risk_event_graph",
        SimpleNamespace(ainvoke=AsyncMock(return_value=graph_state)),
    )
    monkeypatch.setattr("app.services.risk_scan_scheduler.write_assessment", AsyncMock(return_value={"code": 200}))
    monkeypatch.setattr("app.services.risk_scan_scheduler.get_db_service", lambda: db)

    await scheduler._event_scan("ST_CP_LAKE_01", "WATER_LEVEL", "WARNING")

    db.save_emergency_plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_event_scan_reuses_recent_event_plan(monkeypatch):
    scheduler = RiskScanScheduler()
    graph_state = {
        "focus_station_query": "ST_CP_LAKE_01",
        "risk_assessment": RiskAssessment(
            risk_level=RiskLevel.HIGH,
            risk_score=72.0,
            key_risks=["翠屏湖心水位超过危险线"],
        ),
        "overview_data": {
            "active_alarms": [{"level": "CRITICAL", "status": "OPEN", "metric_type": "WATER_LEVEL"}],
            "stations": [{"id": "ST_CP_LAKE_01", "name": "翠屏湖心水位站", "water_level": 4.35}],
        },
        "emergency_plan": EmergencyPlan(plan_id="EP-NEW", plan_name="新生成事件预案"),
        "resource_plan": [],
        "notifications": [],
    }
    db = SimpleNamespace(
        find_recent_event_plan=AsyncMock(return_value={"plan_id": "EP-EXISTING"}),
        save_emergency_plan=AsyncMock(),
        save_resource_allocations=AsyncMock(),
        save_notifications=AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.risk_scan_scheduler.risk_event_graph",
        SimpleNamespace(ainvoke=AsyncMock(return_value=graph_state)),
    )
    monkeypatch.setattr("app.services.risk_scan_scheduler.write_assessment", AsyncMock(return_value={"code": 200}))
    monkeypatch.setattr("app.services.risk_scan_scheduler.get_db_service", lambda: db)
    monkeypatch.setattr("app.services.risk_scan_scheduler.event_window", lambda: "202604301000")

    await scheduler._event_scan("ST_CP_LAKE_01", "WATER_LEVEL", "CRITICAL")

    db.find_recent_event_plan.assert_awaited_once_with(
        station_id="ST_CP_LAKE_01",
        metric_type="WATER_LEVEL",
        risk_level="high",
        since_minutes=30,
    )
    assert db.save_emergency_plan.await_args.kwargs["plan_id"] == "EP-EXISTING"
