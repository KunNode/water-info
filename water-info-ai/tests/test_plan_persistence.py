from __future__ import annotations

from app.services.plan_persistence import (
    SOURCE_EVENT,
    SOURCE_MANUAL,
    build_event_session_id,
    build_trigger_conditions,
    should_persist_plan,
)
from app.state import EmergencyPlan, Evidence, RiskAssessment, RiskLevel


def _state(*, query: str, level: RiskLevel, score: float = 65.0, evidence: bool = False) -> dict:
    evidence_context = []
    if evidence:
        evidence_context = [
            Evidence(
                citation_id="[1]",
                content="III级响应应加密巡查并前置抢险力量。",
                document_title="防汛响应等级划分与启动条件",
            )
        ]
    return {
        "user_query": query,
        "session_id": "session-001",
        "intent": "plan_generation",
        "focus_station_query": "ST_CP_LAKE_01",
        "risk_assessment": RiskAssessment(
            risk_level=level,
            risk_score=score,
            affected_stations=["翠屏湖心水位站"],
            key_risks=["翠屏湖心水位超过警戒线"],
            response_level="III级响应",
        ),
        "overview_data": {
            "active_alarms": [
                {
                    "level": "CRITICAL",
                    "status": "OPEN",
                    "station_name": "翠屏湖心水位站",
                    "metric_type": "WATER_LEVEL",
                    "message": "水位超过危险线",
                }
            ],
            "stations": [
                {
                    "id": "ST_CP_LAKE_01",
                    "code": "ST_CP_LAKE_01",
                    "name": "翠屏湖心水位站",
                    "water_level": 4.35,
                    "warning_level": 3.6,
                    "danger_level": 4.15,
                }
            ],
        },
        "evidence_context": evidence_context,
        "emergency_plan": EmergencyPlan(plan_id="EP-001", plan_name="翠屏湖防汛预案"),
    }


def test_manual_low_risk_plan_request_can_persist():
    state = _state(query="请生成一份防汛应急预案", level=RiskLevel.LOW, score=18.0)

    decision = should_persist_plan(state, source=SOURCE_MANUAL)
    trigger_conditions = build_trigger_conditions(state, source=SOURCE_MANUAL)

    assert decision.should_persist is True
    assert decision.mode == "create"
    assert "manual" in decision.source
    assert "人工请求生成" in trigger_conditions
    assert "当前综合风险为 low" in trigger_conditions
    assert "未达到自动事件入库门槛" in trigger_conditions


def test_manual_risk_question_without_plan_intent_does_not_persist():
    state = _state(query="当前风险严不严重", level=RiskLevel.HIGH)
    state["intent"] = "risk_assessment"

    decision = should_persist_plan(state, source=SOURCE_MANUAL)

    assert decision.should_persist is False
    assert decision.mode == "skip"
    assert "manual request did not ask for a plan" in decision.reason


def test_event_low_risk_plan_is_not_persisted():
    state = _state(query="事件巡检", level=RiskLevel.LOW)

    decision = should_persist_plan(state, source=SOURCE_EVENT)

    assert decision.should_persist is False
    assert decision.mode == "skip"
    assert "risk level low is below event persistence threshold" in decision.reason


def test_event_moderate_plan_with_evidence_can_persist():
    state = _state(query="事件巡检", level=RiskLevel.MODERATE, evidence=True)

    decision = should_persist_plan(state, source=SOURCE_EVENT)
    trigger_conditions = build_trigger_conditions(state, source=SOURCE_EVENT)

    assert decision.should_persist is True
    assert decision.mode == "create"
    assert "event" in decision.source
    assert "来源：自动事件触发" in trigger_conditions
    assert "风险等级：moderate" in trigger_conditions
    assert "翠屏湖心水位站" in trigger_conditions
    assert "最高等级 CRITICAL" in trigger_conditions
    assert "[1]《防汛响应等级划分与启动条件》" in trigger_conditions


def test_event_moderate_without_concrete_evidence_does_not_persist():
    state = _state(query="事件巡检", level=RiskLevel.MODERATE)
    state["focus_station_query"] = ""
    state["overview_data"] = {"active_alarms": [], "stations": []}
    state["evidence_context"] = []
    state["risk_assessment"].affected_stations = []
    state["risk_assessment"].key_risks = []

    decision = should_persist_plan(state, source=SOURCE_EVENT)

    assert decision.should_persist is False
    assert decision.mode == "skip"
    assert "event persistence requires concrete evidence" in decision.reason


def test_trigger_conditions_do_not_fake_citations_when_evidence_is_absent():
    state = _state(query="请生成一份防汛应急预案", level=RiskLevel.HIGH, evidence=False)

    trigger_conditions = build_trigger_conditions(state, source=SOURCE_MANUAL)

    assert "业务依据" not in trigger_conditions
    assert "[1]" not in trigger_conditions


def test_event_session_id_is_stable_for_same_window():
    session_id = build_event_session_id("ST_CP_LAKE_01", "WATER_LEVEL", "2026043010")

    assert session_id == "risk-event:ST_CP_LAKE_01:WATER_LEVEL:2026043010"
