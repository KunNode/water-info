"""API smoke tests for the FastAPI entrypoint."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.state import EmergencyAction, EmergencyPlan, NotificationRecord, ResourceAllocation, RiskAssessment, RiskLevel


class StubGraph:
    def __init__(self, *, final_state: dict | None = None, stream_events: list[dict] | None = None) -> None:
        self.ainvoke = AsyncMock(return_value=final_state or {})
        self._stream_events = stream_events or []

    async def astream(self, *_args, **_kwargs):
        for event in self._stream_events:
            yield event


def _build_db_mock():
    return SimpleNamespace(
        _get_pool=AsyncMock(return_value=object()),
        ensure_plan_tables=AsyncMock(),
        close=AsyncMock(),
        save_emergency_plan=AsyncMock(),
        save_resource_allocations=AsyncMock(),
        save_notifications=AsyncMock(),
    )


def _build_session_mock(history: list[dict] | None = None):
    return SimpleNamespace(
        get_history=AsyncMock(return_value=history or []),
        save_turn=AsyncMock(),
        close=AsyncMock(),
    )


@contextmanager
def _patched_client(*, db_mock=None, session_mock=None, graph=None):
    db_mock = db_mock or _build_db_mock()
    session_mock = session_mock or _build_session_mock()
    graph = graph or StubGraph()

    with ExitStack() as stack:
        stack.enter_context(patch("app.main.get_db_service", return_value=db_mock))
        stack.enter_context(patch("app.main.flood_response_graph", graph))
        stack.enter_context(patch("app.services.session.get_session_service", return_value=session_mock))
        client = stack.enter_context(TestClient(app))
        yield client, db_mock, session_mock, graph


def test_health_endpoint_returns_service_metadata():
    with _patched_client() as (client, db_mock, session_mock, _graph):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "water-info-ai",
        "version": "0.1.0",
    }
    db_mock._get_pool.assert_awaited_once()
    db_mock.ensure_plan_tables.assert_awaited_once()
    db_mock.close.assert_awaited_once()
    session_mock.close.assert_awaited_once()


def test_flood_query_endpoint_returns_aggregated_result_and_persists_turns():
    plan = EmergencyPlan(
        plan_id="EP-001",
        plan_name="城区防汛预案",
        risk_level=RiskLevel.HIGH,
        trigger_conditions="水位接近警戒线",
        actions=[
            EmergencyAction(
                action_id="A-001",
                action_type="patrol",
                description="加密巡查",
                priority=1,
                responsible_dept="防汛办",
                deadline_minutes=30,
            ),
            EmergencyAction(
                action_id="A-002",
                action_type="notification",
                description="通知沿线单位",
                priority=2,
                responsible_dept="应急办",
                deadline_minutes=15,
            ),
        ],
        summary="立即启动高风险响应。",
    )
    final_state = {
        "final_response": "已完成防汛研判并生成响应预案。",
        "risk_assessment": RiskAssessment(
            risk_level=RiskLevel.HIGH,
            risk_score=82.5,
            key_risks=["河道水位持续上涨"],
        ),
        "emergency_plan": plan,
        "resource_plan": [
            ResourceAllocation(
                resource_type="personnel",
                resource_name="抢险队",
                quantity=12,
                source_location="市应急仓库",
                target_location="城区河段",
                eta_minutes=25,
            )
        ],
        "notifications": [
            NotificationRecord(
                target="应急办",
                channel="sms",
                content="请立即进入防汛待命状态。",
            )
        ],
    }
    history = [{"role": "user", "content": "上一轮问题"}]
    graph = StubGraph(final_state=final_state)

    with _patched_client(session_mock=_build_session_mock(history), graph=graph) as (client, db_mock, session_mock, _graph):
        response = client.post(
            "/api/v1/flood/query",
            json={"query": "分析当前水情并生成预案", "session_id": "session-001"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "session-001",
        "response": "已完成防汛研判并生成响应预案。",
        "risk_level": "high",
        "risk_score": 82.5,
        "plan_id": "EP-001",
        "plan_name": "城区防汛预案",
        "actions_count": 2,
        "resources_count": 1,
        "notifications_count": 1,
    }
    graph.ainvoke.assert_awaited_once()
    db_mock.save_emergency_plan.assert_awaited_once()
    db_mock.save_resource_allocations.assert_awaited_once()
    db_mock.save_notifications.assert_awaited_once()
    session_mock.get_history.assert_awaited_once_with("session-001")
    assert session_mock.save_turn.await_count == 2


def test_flood_query_stream_emits_expected_sse_events():
    graph = StubGraph(
        stream_events=[
            {
                "data_analyst": {
                    "data_summary": "两个站点水位上涨。",
                    "messages": [{"role": "data_analyst", "content": "已完成数据分析"}],
                }
            },
            {
                "risk_assessor": {
                    "risk_assessment": RiskAssessment(
                        risk_level=RiskLevel.MODERATE,
                        risk_score=65.0,
                        key_risks=["未来3小时仍有降雨"],
                    ),
                    "messages": [{"role": "risk_assessor", "content": "风险等级为中等"}],
                }
            },
            {
                "final_response": {
                    "final_response": "综合研判已完成。",
                    "messages": [{"role": "final_response", "content": "综合研判已完成。"}],
                }
            },
        ]
    )

    with _patched_client(graph=graph) as (client, _db_mock, _session_mock, _graph):
        with client.stream(
            "POST",
            "/api/v1/flood/query/stream",
            json={"query": "给出当前风险评估", "session_id": "stream-001"},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "session_init"' in body
    assert '"agent": "data_analyst", "status": "active"' in body
    assert '"type": "risk_update"' in body
    assert '"level": "moderate"' in body
    assert '"response": "综合研判已完成。"' in body
    assert '"agent": "__done__", "status": "done"' in body


def test_health_endpoint_still_works_when_database_warmup_fails():
    db_mock = _build_db_mock()
    db_mock._get_pool = AsyncMock(side_effect=RuntimeError("db unavailable"))

    with _patched_client(db_mock=db_mock) as (client, _db_mock, session_mock, _graph):
        response = client.get("/health")

    assert response.status_code == 200
    db_mock.ensure_plan_tables.assert_not_awaited()
    db_mock.close.assert_awaited_once()
    session_mock.close.assert_awaited_once()
