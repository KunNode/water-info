# Emergency Plan Trigger Conditions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single, testable policy that decides when emergency plans are written to the plan library and builds auditable `trigger_conditions` text.

**Architecture:** Keep LangGraph plan generation unchanged, but put persistence decisions behind a new `plan_persistence` service. Manual plan requests create new plans; automatic risk events only persist moderate-or-higher plans with concrete evidence and reuse a recent event plan when possible.

**Tech Stack:** Python 3.11, FastAPI, LangGraph state dataclasses, asyncpg database service, pytest, pytest-asyncio.

---

## File Structure

- Create: `water-info-ai/app/services/plan_persistence.py`
  - Owns `PlanPersistenceDecision`, source constants, manual-intent detection, event evidence checks, event session key generation, and `trigger_conditions` construction.
- Create: `water-info-ai/tests/test_plan_persistence.py`
  - Unit tests for manual writes, automatic event skips, event evidence, low-risk manual trigger text, and no fake citations.
- Modify: `water-info-ai/app/main.py`
  - Calls the policy before `save_emergency_plan`; preserves snapshot writes and API response behavior.
- Modify: `water-info-ai/app/services/risk_scan_scheduler.py`
  - After event AI assessment writeback, asks the policy whether to persist an event plan and saves only when allowed.
- Modify: `water-info-ai/app/database.py`
  - Adds `find_recent_event_plan` to support event-plan reuse without schema changes.
- Modify: `water-info-ai/tests/test_main_api.py`
  - Adds assertions that manual plan requests still persist, while non-plan risk questions do not.
- Create or modify: `water-info-ai/tests/test_risk_scan_scheduler.py`
  - Tests event scan plan persistence, low-risk skip, and recent event plan reuse.

## Task 1: Add The Plan Persistence Policy

**Files:**
- Create: `water-info-ai/app/services/plan_persistence.py`
- Test: `water-info-ai/tests/test_plan_persistence.py`

- [ ] **Step 1: Write the policy unit tests**

Create `water-info-ai/tests/test_plan_persistence.py` with these tests:

```python
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
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
cd water-info-ai
uv run pytest -q tests/test_plan_persistence.py
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'app.services.plan_persistence'`.

- [ ] **Step 3: Implement the policy module**

Create `water-info-ai/app/services/plan_persistence.py`:

```python
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
        citation_id = str(getattr(item, "citation_id", "") or item.get("citation_id", "")).strip()
        title = str(getattr(item, "document_title", "") or item.get("document_title", "")).strip()
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
```

- [ ] **Step 4: Run the policy tests to verify they pass**

Run:

```bash
cd water-info-ai
uv run pytest -q tests/test_plan_persistence.py
```

Expected: `7 passed`.

- [ ] **Step 5: Commit the policy module**

Run:

```bash
git add water-info-ai/app/services/plan_persistence.py water-info-ai/tests/test_plan_persistence.py
git commit -m "Separate plan persistence policy from generation" \
  -m "Plan generation remains inside LangGraph, but persistence now has a single policy boundary that can be tested independently." \
  -m "Constraint: Automatic event plans must require moderate-or-higher risk plus concrete evidence" \
  -m "Rejected: Let plan_generator own trigger_conditions | model-authored text is not stable enough for audit fields" \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: uv run pytest -q tests/test_plan_persistence.py"
```

## Task 2: Gate Manual Query Plan Persistence

**Files:**
- Modify: `water-info-ai/app/main.py`
- Modify: `water-info-ai/tests/test_main_api.py`

- [ ] **Step 1: Add the non-plan persistence regression test**

Append this test to `water-info-ai/tests/test_main_api.py`:

```python
def test_flood_query_does_not_persist_plan_for_non_plan_manual_query():
    plan = EmergencyPlan(
        plan_id="EP-RISK-ONLY",
        plan_name="中间态预案",
        risk_level=RiskLevel.HIGH,
        trigger_conditions="模型中间态",
        actions=[
            EmergencyAction(
                action_id="A-001",
                action_type="monitoring",
                description="加密监测",
                priority=2,
                responsible_dept="监测调度科",
            )
        ],
    )
    final_state = {
        "final_response": "当前风险较高，请关注水位变化。",
        "intent": "risk_assessment",
        "risk_assessment": RiskAssessment(
            risk_level=RiskLevel.HIGH,
            risk_score=72.0,
            key_risks=["水位持续上涨"],
        ),
        "emergency_plan": plan,
    }
    graph = StubGraph(final_state=final_state)

    with _patched_client(graph=graph) as (client, db_mock, _session_mock, _graph):
        response = client.post(
            "/api/v1/flood/query",
            json={"query": "当前风险严不严重", "session_id": "session-risk-only"},
        )

    assert response.status_code == 200
    assert response.json()["plan_id"] == "EP-RISK-ONLY"
    db_mock.save_conversation_snapshot.assert_awaited_once()
    db_mock.save_emergency_plan.assert_not_awaited()
    db_mock.save_resource_allocations.assert_not_awaited()
    db_mock.save_notifications.assert_not_awaited()
```

- [ ] **Step 2: Update the existing manual plan test expectation**

In `test_flood_query_endpoint_returns_aggregated_result_and_persists_turns`, after `db_mock.save_emergency_plan.assert_awaited_once()`, add:

```python
    saved_kwargs = db_mock.save_emergency_plan.await_args.kwargs
    assert "摘要：" in saved_kwargs["trigger_conditions"]
    assert "来源：人工对话请求" in saved_kwargs["trigger_conditions"]
```

- [ ] **Step 3: Run main API tests to verify the new behavior fails**

Run:

```bash
cd water-info-ai
uv run pytest -q tests/test_main_api.py::test_flood_query_does_not_persist_plan_for_non_plan_manual_query tests/test_main_api.py::test_flood_query_endpoint_returns_aggregated_result_and_persists_turns
```

Expected: the new test FAILS because `_persist_result()` still saves every plan.

- [ ] **Step 4: Modify `_persist_result()` to use the policy**

In `water-info-ai/app/main.py`, add this import near the other service imports:

```python
from app.services.plan_persistence import SOURCE_MANUAL, build_trigger_conditions, should_persist_plan
```

Then replace the `if not plan: return` and plan-save block in `_persist_result()` with:

```python
    if not plan:
        return

    decision = should_persist_plan(graph_state, source=SOURCE_MANUAL)
    if not decision.should_persist:
        logger.info("[%s] plan persist skipped: %s", session_id, decision.reason)
        return

    try:
        trigger_conditions = build_trigger_conditions(graph_state, source=SOURCE_MANUAL)
        plan.trigger_conditions = trigger_conditions
        await db.save_emergency_plan(
            plan_id=decision.plan_id or plan.plan_id,
            plan_name=plan.plan_name or "防汛应急预案",
            risk_level=risk_level,
            trigger_conditions=trigger_conditions,
            status=plan.status or "draft",
            session_id=session_id,
            summary=(graph_state.get("final_response") or plan.summary or "")[:2000],
            actions=[asdict(action) for action in plan.actions],
        )
        resources = [asdict(resource) for resource in graph_state.get("resource_plan", [])]
        notifications = [asdict(record) for record in graph_state.get("notifications", [])]
        if resources:
            await db.save_resource_allocations(plan.plan_id, resources)
        if notifications:
            await db.save_notifications(plan.plan_id, notifications)
    except Exception as exc:
        logger.warning("[%s] plan persist failed (non-fatal): %s", session_id, exc)
```

- [ ] **Step 5: Run the focused API tests**

Run:

```bash
cd water-info-ai
uv run pytest -q tests/test_main_api.py::test_flood_query_does_not_persist_plan_for_non_plan_manual_query tests/test_main_api.py::test_flood_query_endpoint_returns_aggregated_result_and_persists_turns
```

Expected: `2 passed`.

- [ ] **Step 6: Run the full main API smoke tests**

Run:

```bash
cd water-info-ai
uv run pytest -q tests/test_main_api.py
```

Expected: all tests in `tests/test_main_api.py` pass.

- [ ] **Step 7: Commit the manual persistence gate**

Run:

```bash
git add water-info-ai/app/main.py water-info-ai/tests/test_main_api.py
git commit -m "Gate manual plan persistence through policy" \
  -m "Manual graph responses may contain plan objects, but only explicit plan requests should write to the plan library." \
  -m "Constraint: Conversation snapshots must still persist even when plan writes are skipped" \
  -m "Rejected: Hide plan_id from API response when persistence skips | existing frontend behavior expects generated plan metadata" \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Tested: uv run pytest -q tests/test_main_api.py"
```

## Task 3: Add Event Plan Lookup Support

**Files:**
- Modify: `water-info-ai/app/database.py`
- Test: `water-info-ai/tests/test_plan_persistence.py`

- [ ] **Step 1: Add a pure event identity helper test**

Add this test to `water-info-ai/tests/test_plan_persistence.py`:

```python
from app.services.plan_persistence import event_window


def test_event_window_uses_30_minute_buckets():
    assert event_window("2026-04-30T10:14:00") == "202604301000"
    assert event_window("2026-04-30T10:44:00") == "202604301030"
```

- [ ] **Step 2: Run the helper test to verify it fails**

Run:

```bash
cd water-info-ai
uv run pytest -q tests/test_plan_persistence.py::test_event_window_uses_30_minute_buckets
```

Expected: FAIL with `ImportError` for `event_window`.

- [ ] **Step 3: Implement the event window helper**

In `water-info-ai/app/services/plan_persistence.py`, add `event_window` below `build_event_session_id`:

```python
def event_window(iso_timestamp: str | None = None) -> str:
    if iso_timestamp:
        parsed = datetime.fromisoformat(iso_timestamp)
    else:
        parsed = datetime.now()
    minute = 0 if parsed.minute < 30 else 30
    return parsed.replace(minute=minute, second=0, microsecond=0).strftime("%Y%m%d%H%M")
```

- [ ] **Step 4: Run policy tests**

Run:

```bash
cd water-info-ai
uv run pytest -q tests/test_plan_persistence.py
```

Expected: all policy tests pass.

- [ ] **Step 5: Add database lookup method**

In `water-info-ai/app/database.py`, add this method after `get_plans_by_session`:

```python
    async def find_recent_event_plan(
        self,
        *,
        station_id: str,
        metric_type: str,
        risk_level: str,
        since_minutes: int = 30,
    ) -> dict | None:
        session_prefix = f"risk-event:{station_id}:{metric_type}:"
        return await self._fetchrow("""
            SELECT plan_id, plan_name, risk_level, status, session_id, created_at
            FROM emergency_plan
            WHERE session_id LIKE $1
              AND risk_level = $2
              AND status IN ('draft', 'executing')
              AND created_at >= NOW() - ($3::int * INTERVAL '1 minute')
            ORDER BY created_at DESC
            LIMIT 1
        """, f"{session_prefix}%", risk_level, since_minutes)
```

- [ ] **Step 6: Run a Python compile check**

Run:

```bash
cd water-info-ai
uv run python -m py_compile app/database.py app/services/plan_persistence.py
```

Expected: command exits with status 0 and prints no output.

- [ ] **Step 7: Commit the event lookup support**

Run:

```bash
git add water-info-ai/app/database.py water-info-ai/app/services/plan_persistence.py water-info-ai/tests/test_plan_persistence.py
git commit -m "Add event plan identity support" \
  -m "Automatic event plans need a stable application-layer identity before schema-level event keys are introduced." \
  -m "Constraint: First implementation phase avoids database schema changes" \
  -m "Rejected: Add source/event_key columns immediately | the design keeps schema changes as a later hardening step" \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: uv run pytest -q tests/test_plan_persistence.py; uv run python -m py_compile app/database.py app/services/plan_persistence.py"
```

## Task 4: Persist Automatic Event Plans Through The Policy

**Files:**
- Modify: `water-info-ai/app/services/risk_scan_scheduler.py`
- Create or modify: `water-info-ai/tests/test_risk_scan_scheduler.py`

- [ ] **Step 1: Write scheduler event persistence tests**

Create `water-info-ai/tests/test_risk_scan_scheduler.py` with:

```python
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
    monkeypatch.setattr("app.services.risk_scan_scheduler.risk_event_graph", SimpleNamespace(ainvoke=AsyncMock(return_value=graph_state)))
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
    monkeypatch.setattr("app.services.risk_scan_scheduler.risk_event_graph", SimpleNamespace(ainvoke=AsyncMock(return_value=graph_state)))
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
    monkeypatch.setattr("app.services.risk_scan_scheduler.risk_event_graph", SimpleNamespace(ainvoke=AsyncMock(return_value=graph_state)))
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
```

- [ ] **Step 2: Run scheduler tests to verify they fail**

Run:

```bash
cd water-info-ai
uv run pytest -q tests/test_risk_scan_scheduler.py
```

Expected: FAIL because `_event_scan()` writes only AI assessments and does not call `save_emergency_plan`.

- [ ] **Step 3: Add policy imports to the scheduler**

In `water-info-ai/app/services/risk_scan_scheduler.py`, add:

```python
from dataclasses import asdict

from app.services.plan_persistence import (
    SOURCE_EVENT,
    build_event_session_id,
    build_trigger_conditions,
    event_window,
    should_persist_plan,
)
```

- [ ] **Step 4: Add an event-plan persistence helper**

In `RiskScanScheduler`, add this method below `_event_scan`:

```python
    async def _persist_event_plan(self, state: dict, *, station_id: str, metric_type: str) -> None:
        decision = should_persist_plan(state, source=SOURCE_EVENT)
        if not decision.should_persist:
            logger.info("Event plan persist skipped: station=%s metric=%s reason=%s", station_id, metric_type, decision.reason)
            return

        plan = state.get("emergency_plan")
        if not plan:
            return

        assessment = state.get("risk_assessment")
        risk_level = str(getattr(getattr(assessment, "risk_level", None), "value", getattr(assessment, "risk_level", "none")) or "none")
        db = get_db_service()
        existing = await db.find_recent_event_plan(
            station_id=station_id,
            metric_type=metric_type,
            risk_level=risk_level,
            since_minutes=30,
        )
        plan_id = str(existing["plan_id"]) if existing else plan.plan_id
        session_id = build_event_session_id(station_id, metric_type, event_window())
        trigger_conditions = build_trigger_conditions(state, source=SOURCE_EVENT)
        plan.trigger_conditions = trigger_conditions

        await db.save_emergency_plan(
            plan_id=plan_id,
            plan_name=plan.plan_name or "自动事件防汛应急预案",
            risk_level=risk_level,
            trigger_conditions=trigger_conditions,
            status=plan.status or "draft",
            session_id=session_id,
            summary=(state.get("final_response") or plan.summary or "")[:2000],
            actions=[asdict(action) for action in plan.actions],
        )

        resources = [asdict(resource) for resource in state.get("resource_plan", [])]
        notifications = [asdict(record) for record in state.get("notifications", [])]
        if resources:
            await db.save_resource_allocations(plan_id, resources)
        if notifications:
            await db.save_notifications(plan_id, notifications)
```

- [ ] **Step 5: Call the helper from `_event_scan()`**

In `_event_scan()`, after:

```python
                await write_assessment(result, source="EVENT", station_id=station_id, metric_type=metric_type)
```

add:

```python
                await self._persist_event_plan(result, station_id=station_id, metric_type=metric_type)
```

- [ ] **Step 6: Run scheduler tests**

Run:

```bash
cd water-info-ai
uv run pytest -q tests/test_risk_scan_scheduler.py
```

Expected: `3 passed`.

- [ ] **Step 7: Run policy and scheduler tests together**

Run:

```bash
cd water-info-ai
uv run pytest -q tests/test_plan_persistence.py tests/test_risk_scan_scheduler.py
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit event persistence**

Run:

```bash
git add water-info-ai/app/services/risk_scan_scheduler.py water-info-ai/tests/test_risk_scan_scheduler.py
git commit -m "Persist eligible event-generated emergency plans" \
  -m "Risk event scans now write event plans only after the shared policy confirms risk level and evidence, and they reuse recent event plans to reduce duplicate library entries." \
  -m "Constraint: AI assessment writeback remains independent from plan persistence" \
  -m "Rejected: Persist all event graph plans | low-risk and evidence-poor events would pollute the plan library" \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Tested: uv run pytest -q tests/test_plan_persistence.py tests/test_risk_scan_scheduler.py"
```

## Task 5: Final Regression Pass

**Files:**
- Verify only unless failures require fixes in files already touched.

- [ ] **Step 1: Run the core AI test subset**

Run:

```bash
cd water-info-ai
uv run pytest -q tests/test_plan_persistence.py tests/test_main_api.py tests/test_risk_scan_scheduler.py tests/test_agents.py tests/test_supervisor_routing.py
```

Expected: all selected tests pass.

- [ ] **Step 2: Run a compile check on touched Python modules**

Run:

```bash
cd water-info-ai
uv run python -m py_compile app/main.py app/database.py app/services/plan_persistence.py app/services/risk_scan_scheduler.py
```

Expected: command exits with status 0 and prints no output.

- [ ] **Step 3: Inspect the working tree**

Run:

```bash
git status --short
```

Expected: only intended files are modified. The pre-existing `.superpowers/brainstorm/23551-1777428781/` state file changes may still be present and should not be committed with implementation changes.

- [ ] **Step 4: Final commit if regression fixes were needed**

If Step 1 or Step 2 required small fixes after Task 4, commit only those fixes:

```bash
git add water-info-ai/app water-info-ai/tests
git commit -m "Stabilize emergency plan persistence regressions" \
  -m "This commit contains small follow-up fixes found by the final focused AI test subset." \
  -m "Constraint: Keep unrelated workspace state files out of the commit" \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: uv run pytest -q tests/test_plan_persistence.py tests/test_main_api.py tests/test_risk_scan_scheduler.py tests/test_agents.py tests/test_supervisor_routing.py; uv run python -m py_compile app/main.py app/database.py app/services/plan_persistence.py app/services/risk_scan_scheduler.py"
```

## Self-Review Notes

- Spec coverage:
  - Manual versus automatic persistence is implemented in Task 1 and wired in Task 2 and Task 4.
  - Automatic event threshold `moderate/high/critical` plus evidence is covered by Task 1 tests.
  - Manual low-risk plan persistence is covered by Task 1 and Task 2.
  - Event merge without schema changes is covered by Task 3 and Task 4.
  - `trigger_conditions` summary plus structured evidence is covered by Task 1 tests and used in Task 2 and Task 4.
- Scope:
  - No Spring schema changes.
  - No frontend changes.
  - No risk scoring changes.
- Verification:
  - Focused policy, API, scheduler, agent, and supervisor tests are listed in Task 5.
