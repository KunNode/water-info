"""API smoke tests for the FastAPI entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import _build_stream_events, _reasoning_steps_from_final_state, _tool_calls_from_traces, app
from app.rag.models import SearchResult
from app.state import EmergencyAction, EmergencyPlan, NotificationRecord, ResourceAllocation, RiskAssessment, RiskLevel

pytestmark = pytest.mark.smoke


class StubGraph:
    def __init__(self, *, final_state: dict | None = None, stream_events: list[dict] | None = None) -> None:
        self.ainvoke = AsyncMock(return_value=final_state or {})
        self._stream_events = stream_events or []

    async def astream(self, *_args, **_kwargs):
        for event in self._stream_events:
            yield event


class SlowStreamGraph:
    def __init__(self) -> None:
        self.ainvoke = AsyncMock(return_value={})

    async def astream(self, *_args, **_kwargs):
        await asyncio.sleep(0.03)
        yield {
            "final_response": {
                "final_response": "延迟完成。",
                "messages": [{"role": "final_response", "content": "延迟完成。"}],
            }
        }


def _build_db_mock():
    return SimpleNamespace(
        _get_pool=AsyncMock(return_value=object()),
        ensure_plan_tables=AsyncMock(),
        ensure_conversation_tables=AsyncMock(),
        ensure_kb_tables=AsyncMock(),
        close=AsyncMock(),
        ensure_or_create_session=AsyncMock(),
        save_conversation_message=AsyncMock(side_effect=[101, 102, 103]),
        update_message_content=AsyncMock(),
        get_conversation_messages=AsyncMock(return_value=[]),
        save_conversation_snapshot=AsyncMock(),
        save_emergency_plan=AsyncMock(),
        save_resource_allocations=AsyncMock(),
        save_notifications=AsyncMock(),
        list_kb_documents=AsyncMock(return_value=[]),
        get_kb_document=AsyncMock(return_value=None),
        soft_delete_kb_document=AsyncMock(return_value=True),
        get_kb_stats=AsyncMock(return_value={
            "document_count": 0,
            "ready_document_count": 0,
            "chunk_count": 0,
            "job_success_rate": 0.0,
            "model_distribution": {},
        }),
        create_kb_ingest_job=AsyncMock(return_value="job-001"),
        list_memory_items=AsyncMock(return_value=[]),
        update_memory_item=AsyncMock(return_value=None),
        delete_memory_item=AsyncMock(return_value=True),
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
    db_mock.ensure_kb_tables.assert_awaited_once()
    db_mock.close.assert_awaited_once()
    session_mock.close.assert_awaited_once()


def test_stream_events_do_not_duplicate_final_response_content():
    events = _build_stream_events(
        "conversation_assistant",
        {
            "final_response": "你好，我是防汛智能助手。",
            "messages": [{"role": "conversation_assistant", "content": "你好，我是防汛智能助手。"}],
        },
    )

    message_events = [event for event in events if event["type"] == "agent_message"]
    assert message_events == [
        {
            "type": "agent_message",
            "agent": "final_response",
            "content": "你好，我是防汛智能助手。",
            "response": "你好，我是防汛智能助手。",
        }
    ]


def test_stream_events_suppress_draft_message_to_avoid_double_send():
    events = _build_stream_events(
        "conversation_assistant",
        {
            "final_response_draft": "你好，我是防汛智能助手。",
            "messages": [{"role": "conversation_assistant", "content": "你好，我是防汛智能助手。"}],
        },
    )

    message_events = [event for event in events if event["type"] == "agent_message"]
    assert message_events == []
    # Activity signals (active/done) should still be emitted so the UI shows progress.
    assert any(
        event["type"] == "agent_update" and event["status"] == "active"
        for event in events
    )


def test_stream_events_suppress_intermediate_agent_messages():
    events = _build_stream_events(
        "data_analyst",
        {
            "data_summary": "北闸站最新水位 4.248m。",
            "messages": [{"role": "data_analyst", "content": "北闸站最新水位 4.248m。"}],
        },
    )

    assert [event for event in events if event["type"] == "agent_message"] == []


def test_stream_events_emit_trace_update_when_traces_present():
    events = _build_stream_events(
        "data_analyst",
        {
            "data_summary": "概览",
            "messages": [{"role": "data_analyst", "content": "概览"}],
            "execution_traces": [
                {
                    "phase": "tool_call",
                    "status": "completed",
                    "title": "获取水情概览",
                    "detail": "5 个站点",
                    "tool_name": "get_flood_situation_overview",
                    "metadata": {"duration_ms": 42},
                },
            ],
        },
    )

    trace_events = [e for e in events if e["type"] == "trace_update"]
    assert len(trace_events) == 1
    assert trace_events[0]["phase"] == "tool_call"
    assert trace_events[0]["title"] == "获取水情概览"
    assert trace_events[0]["detail"] == "5 个站点"
    assert trace_events[0]["tool_name"] == "get_flood_situation_overview"
    assert trace_events[0]["metadata"]["duration_ms"] == 42


def test_stream_events_no_trace_update_when_no_traces():
    events = _build_stream_events(
        "data_analyst",
        {
            "data_summary": "概览",
            "messages": [{"role": "data_analyst", "content": "概览"}],
        },
    )

    trace_events = [e for e in events if e["type"] == "trace_update"]
    assert trace_events == []



def test_reasoning_steps_merges_thought_and_tool_traces():
    final_state = {
        "execution_traces": [
            {
                "phase": "risk_assessment",
                "status": "completed",
                "title": "意图识别: risk_assessment",
                "detail": "焦点站点: 翠屏湖",
                "tool_name": None,
                "metadata": {"duration_ms": 120},
            },
            {
                "phase": "tool_call",
                "status": "completed",
                "title": "查询站点总览",
                "detail": "返回 3 条观测",
                "tool_name": "get_station_overview",
                "metadata": {
                    "duration_ms": 42,
                    "input_summary": "station_code=FRONT-01",
                    "output_summary": "3 站点",
                },
            },
        ],
    }

    steps = _reasoning_steps_from_final_state(final_state)

    assert [s["kind"] for s in steps] == ["thought", "tool"]
    assert steps[0]["status"] == "success"
    assert steps[0]["title"] == "意图识别: risk_assessment"
    assert steps[0]["content"] == "焦点站点: 翠屏湖"
    assert steps[0]["duration_ms"] == 120
    assert "tool" not in steps[0]

    assert steps[1]["status"] == "success"
    assert steps[1]["duration_ms"] == 42
    assert steps[1]["tool"] == {
        "name": "get_station_overview",
        "display_name": "查询站点总览",
        "input_summary": "station_code=FRONT-01",
        "result_summary": "3 站点",
    }


def test_reasoning_steps_normalizes_status_and_defaults():
    final_state = {
        "execution_traces": [
            {"phase": "final_response", "status": "failed", "title": "post-check", "tool_name": None},
            {"phase": "data_query", "status": "running", "title": "fetching", "metadata": {}},
            {"phase": "final_response"},  # missing title/status/detail
            "not-a-dict",  # must be skipped
        ],
    }

    steps = _reasoning_steps_from_final_state(final_state)

    assert len(steps) == 3
    assert steps[0]["status"] == "error"
    assert steps[1]["status"] == "running"
    assert steps[2]["status"] == "success"
    assert steps[2]["title"] == ""
    assert steps[2]["content"] == ""
    # Unique ids per step
    assert len({s["id"] for s in steps}) == 3


def test_reasoning_steps_returns_empty_for_missing_or_bad_input():
    assert _reasoning_steps_from_final_state({}) == []
    assert _reasoning_steps_from_final_state({"execution_traces": []}) == []
    assert _reasoning_steps_from_final_state(None) == []  # type: ignore[arg-type]


def test_tool_calls_from_traces_flattens_only_tool_entries():
    traces = [
        {
            "phase": "risk_assessment",
            "status": "completed",
            "title": "意图识别",
            "tool_name": None,
            "metadata": {"duration_ms": 11},
        },
        {
            "phase": "tool_call",
            "status": "completed",
            "title": "查询水情概览",
            "detail": "返回 5 站点",
            "tool_name": "get_flood_situation_overview",
            "metadata": {
                "duration_ms": 84,
                "input_summary": "limit=20",
                "output_summary": "5 站点, 2 告警",
            },
        },
        {
            "phase": "tool_call",
            "status": "failed",
            "title": "获取最新观测",
            "detail": "connection timeout",
            "tool_name": "get_recent_observations",
            "metadata": {"duration_ms": 1500, "input_summary": "station_code=X"},
        },
    ]

    calls = _tool_calls_from_traces(traces)

    assert len(calls) == 2
    assert calls[0]["tool_name"] == "get_flood_situation_overview"
    assert calls[0]["arguments"] == {"input_summary": "limit=20"}
    assert calls[0]["result"] == {"output_summary": "5 站点, 2 告警"}
    assert calls[0]["error"] is None
    assert calls[0]["duration_ms"] == 84

    assert calls[1]["tool_name"] == "get_recent_observations"
    assert calls[1]["error"] == "connection timeout"
    assert calls[1]["duration_ms"] == 1500
    assert calls[1]["result"] == {}

    # Unique ids per call
    assert len({c["tool_call_id"] for c in calls}) == 2


def test_tool_calls_from_traces_handles_empty_and_malformed_input():
    assert _tool_calls_from_traces(None) == []
    assert _tool_calls_from_traces([]) == []
    assert _tool_calls_from_traces([{"phase": "risk_assessment"}]) == []  # no tool_name
    assert _tool_calls_from_traces(["nope", 1, None]) == []  # type: ignore[list-item]



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
    saved_kwargs = db_mock.save_emergency_plan.await_args.kwargs
    assert "摘要：" in saved_kwargs["trigger_conditions"]
    assert "来源：人工对话请求" in saved_kwargs["trigger_conditions"]
    db_mock.save_resource_allocations.assert_awaited_once()
    db_mock.save_notifications.assert_awaited_once()
    session_mock.get_history.assert_awaited_once_with("session-001")
    assert session_mock.save_turn.await_count == 2
    session_mock.save_turn.assert_any_await("session-001", "user", "分析当前水情并生成预案")
    session_mock.save_turn.assert_any_await("session-001", "assistant", "已完成防汛研判并生成响应预案。")
    assert db_mock.save_conversation_message.await_count == 2


def test_flood_query_uses_database_history_when_redis_history_is_empty():
    db_mock = _build_db_mock()
    db_mock.get_conversation_messages = AsyncMock(return_value=[
        {"role": "user", "content": "上一轮要求关注北闸站", "status": "completed"},
        {"role": "assistant", "content": "已记录北闸站为重点。", "status": "completed"},
        {"role": "assistant", "content": "", "status": "streaming"},
    ])
    session_mock = _build_session_mock(history=[])
    graph = StubGraph(final_state={"final_response": "我会延续上一轮北闸站上下文。"})

    with _patched_client(db_mock=db_mock, session_mock=session_mock, graph=graph) as (client, _db, _session, _graph):
        response = client.post(
            "/api/v1/flood/query",
            json={"query": "继续刚才的问题", "session_id": "session-db-history"},
        )

    assert response.status_code == 200
    initial_state = graph.ainvoke.await_args.args[0]
    assert initial_state["messages"] == [
        {"role": "user", "content": "上一轮要求关注北闸站"},
        {"role": "assistant", "content": "已记录北闸站为重点。"},
        {"role": "user", "content": "继续刚才的问题"},
    ]
    session_mock.save_turn.assert_any_await("session-db-history", "user", "继续刚才的问题")
    session_mock.save_turn.assert_any_await("session-db-history", "assistant", "我会延续上一轮北闸站上下文。")


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
                    "evidence": [
                        {
                            "citation_id": "[1]",
                            "content": "III 级响应要求提前巡查重点堤段。",
                            "document_title": "防汛值班手册",
                            "source_uri": "manual://duty",
                            "heading_path": ["III 级响应"],
                            "score": 0.93,
                        }
                    ],
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
    assert '"type": "evidence_update"' in body
    assert '"level": "moderate"' in body
    assert '"response": "综合研判已完成。"' in body
    assert '"agent": "__done__", "status": "done"' in body


def test_flood_query_stream_emits_structured_error_when_memory_load_fails():
    """When memory_loader_node short-circuits with memory_load_failed, the SSE
    stream must emit a single ``{type: error, code: memory_load_failed,
    recoverable: false}`` event, mark the assistant message as failed, and stop
    before emitting the ``__done__`` agent_update (Req 4.4).
    """
    graph = StubGraph(
        stream_events=[
            {
                "memory_loader": {
                    "memory_context": {},
                    "error": "memory_load_failed: conversation_messages",
                    "next_agent": "__end__",
                    "current_agent": "memory_loader",
                }
            },
            # Any subsequent updates must NOT be processed after the error.
            {
                "final_response": {
                    "final_response": "should not be emitted",
                    "messages": [{"role": "final_response", "content": "nope"}],
                }
            },
        ]
    )

    with _patched_client(graph=graph) as (client, db_mock, _session_mock, _graph):
        with client.stream(
            "POST",
            "/api/v1/flood/query/stream",
            json={"query": "继续研判", "session_id": "stream-mem-fail-001"},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    # Exactly one structured error event with recoverable=false
    assert body.count('"type": "error"') == 1
    assert '"code": "memory_load_failed"' in body
    assert '"recoverable": false' in body
    assert '"message": "会话历史加载失败' in body
    # Must not emit __done__ after the error (stream terminates early)
    assert '"agent": "__done__"' not in body
    # Must not emit the post-error final_response content either
    assert "should not be emitted" not in body

    # The assistant placeholder must be marked failed with the user-facing text.
    db_mock.update_message_content.assert_awaited_once()
    call = db_mock.update_message_content.await_args
    assert call.kwargs["status"] == "failed"
    assert call.args[1] == "会话历史加载失败，请稍后重试"


def test_flood_query_stream_keepalive_does_not_cancel_graph_iteration():
    with (
        patch("app.main.STREAM_KEEPALIVE_INTERVAL", 0.01),
        _patched_client(graph=SlowStreamGraph()) as (client, _db_mock, _session_mock, _graph),
    ):
        with client.stream(
            "POST",
            "/api/v1/flood/query/stream",
            json={"query": "当前总体水情怎么样", "session_id": "stream-slow-001"},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert ":keepalive" in body
    assert '"response": "延迟完成。"' in body
    assert '"agent": "__done__", "status": "done"' in body


def test_flood_query_stream_writes_full_metadata_contract_on_completion():
    """event_stream() must persist the JSONB metadata contract from design §1.

    After the graph completes the stream, update_message_content should be
    invoked once with a metadata dict that contains:

    * ``version == 1``
    * ``agent`` === ``final_state["current_agent"]`` (or "final_response" fallback)
    * ``reasoning_steps`` derived from execution_traces
    * ``execution_traces`` passed through verbatim
    * ``tool_calls`` flattened from tool-class traces

    This guards the end-to-end write-back contract so the front-end
    ``loadSession`` deserializer can rebuild the reasoning chain losslessly.
    """
    graph = StubGraph(
        stream_events=[
            {
                "data_analyst": {
                    "data_summary": "北闸站水位 4.20m。",
                    "messages": [{"role": "data_analyst", "content": "数据分析完成"}],
                    "execution_traces": [
                        {
                            "phase": "tool_call",
                            "status": "completed",
                            "title": "获取水情概览",
                            "detail": "返回 5 站点",
                            "tool_name": "get_flood_situation_overview",
                            "metadata": {
                                "duration_ms": 42,
                                "input_summary": "limit=20",
                                "output_summary": "5 站点",
                            },
                        },
                    ],
                    "current_agent": "data_analyst",
                }
            },
            {
                "final_response": {
                    "final_response": "综合研判已完成。",
                    "messages": [{"role": "final_response", "content": "综合研判已完成。"}],
                    "current_agent": "risk_assessor",
                }
            },
        ]
    )

    with _patched_client(graph=graph) as (client, db_mock, _session_mock, _graph):
        with client.stream(
            "POST",
            "/api/v1/flood/query/stream",
            json={"query": "给出当前风险评估", "session_id": "stream-meta-001"},
        ) as response:
            # Drain the stream so event_stream() runs its completion branch.
            "".join(response.iter_text())

    db_mock.update_message_content.assert_awaited_once()
    call = db_mock.update_message_content.await_args
    # positional: (message_id, content)
    assert call.args[1] == "综合研判已完成。"
    assert call.kwargs["status"] == "completed"
    metadata = call.kwargs["metadata"]
    assert metadata["version"] == 1
    # current_agent from the latest graph update wins (merge order in event_stream)
    assert metadata["agent"] == "risk_assessor"
    # execution_traces pass through from the graph state
    assert len(metadata["execution_traces"]) == 1
    assert metadata["execution_traces"][0]["tool_name"] == "get_flood_situation_overview"
    # reasoning_steps derived from traces
    assert isinstance(metadata["reasoning_steps"], list)
    assert len(metadata["reasoning_steps"]) == 1
    assert metadata["reasoning_steps"][0]["kind"] == "tool"
    assert metadata["reasoning_steps"][0]["tool"]["name"] == "get_flood_situation_overview"
    # tool_calls flattened from the same traces
    assert len(metadata["tool_calls"]) == 1
    assert metadata["tool_calls"][0]["tool_name"] == "get_flood_situation_overview"
    assert metadata["tool_calls"][0]["duration_ms"] == 42


def test_flood_query_stream_metadata_agent_defaults_when_current_agent_missing():
    """When the graph state omits current_agent, metadata.agent falls back to "final_response"."""
    graph = StubGraph(
        stream_events=[
            {
                "final_response": {
                    "final_response": "已完成。",
                    "messages": [{"role": "final_response", "content": "已完成。"}],
                    # intentionally NO current_agent key
                }
            },
        ]
    )

    with _patched_client(graph=graph) as (client, db_mock, _session_mock, _graph):
        with client.stream(
            "POST",
            "/api/v1/flood/query/stream",
            json={"query": "继续研判", "session_id": "stream-meta-002"},
        ) as response:
            "".join(response.iter_text())

    db_mock.update_message_content.assert_awaited_once()
    metadata = db_mock.update_message_content.await_args.kwargs["metadata"]
    assert metadata["agent"] == "final_response"
    assert metadata["version"] == 1
    # No traces -> still emit empty arrays (schema-stable payload)
    assert metadata["execution_traces"] == []
    assert metadata["reasoning_steps"] == []
    assert metadata["tool_calls"] == []


def test_health_endpoint_still_works_when_database_warmup_fails():
    db_mock = _build_db_mock()
    db_mock._get_pool = AsyncMock(side_effect=RuntimeError("db unavailable"))

    with _patched_client(db_mock=db_mock) as (client, _db_mock, session_mock, _graph):
        response = client.get("/health")

    assert response.status_code == 200
    db_mock.ensure_plan_tables.assert_not_awaited()
    db_mock.ensure_kb_tables.assert_not_awaited()
    db_mock.close.assert_awaited_once()
    session_mock.close.assert_awaited_once()


def test_kb_upload_endpoint_creates_job_and_schedules_ingest():
    service = SimpleNamespace(
        create_upload_job=AsyncMock(return_value=("doc-001", "job-001")),
        ingest_document_bytes=AsyncMock(),
    )

    with ExitStack() as stack:
        db_mock = _build_db_mock()
        session_mock = _build_session_mock()
        stack.enter_context(patch("app.main.get_db_service", return_value=db_mock))
        stack.enter_context(patch("app.main.get_knowledge_base_service", return_value=service))
        stack.enter_context(patch("app.services.session.get_session_service", return_value=session_mock))
        client = stack.enter_context(TestClient(app))
        response = client.post(
            "/api/v1/kb/documents",
            headers={"X-User-Id": "u-1", "X-Username": "admin"},
            files={"file": ("guide.md", b"# guide\ncontent", "text/markdown")},
        )

    assert response.status_code == 200
    assert response.json()["document_id"] == "doc-001"
    service.create_upload_job.assert_awaited_once()
    service.ingest_document_bytes.assert_awaited_once()


def test_kb_search_endpoint_returns_serialized_hits():
    service = SimpleNamespace(
        search=AsyncMock(return_value=[
            SearchResult(
                chunk_id="chunk-001",
                document_id="doc-001",
                document_title="防汛值班手册",
                source_uri="manual://duty",
                content="III 级响应下要先完成重点巡查。",
                heading_path=["III 级响应"],
                score=0.91,
                vector_score=0.91,
            )
        ])
    )

    with ExitStack() as stack:
        db_mock = _build_db_mock()
        session_mock = _build_session_mock()
        stack.enter_context(patch("app.main.get_db_service", return_value=db_mock))
        stack.enter_context(patch("app.main.get_knowledge_base_service", return_value=service))
        stack.enter_context(patch("app.services.session.get_session_service", return_value=session_mock))
        client = stack.enter_context(TestClient(app))
        response = client.post("/api/v1/kb/search", json={"query": "III级响应是什么", "top_k": 3})

    assert response.status_code == 200
    assert response.json()[0]["document_title"] == "防汛值班手册"
    service.search.assert_awaited_once()


def test_memory_endpoint_lists_visible_memories():
    db_mock = _build_db_mock()
    db_mock.list_memory_items = AsyncMock(return_value=[
        {
            "id": 7,
            "namespace": "user:u-1:flood_assistant",
            "item_type": "preference",
            "content": "用户偏好先看翠屏湖站点。",
            "importance": 0.8,
            "confidence": 0.9,
            "metadata": {"reason": "test"},
            "source_session_id": "session-001",
            "updated_at": "2026-05-02T00:00:00+00:00",
        }
    ])
    with _patched_client(db_mock=db_mock) as (client, _db_mock, _session_mock, _graph):
        response = client.get("/api/v1/memory?session_id=session-001", headers={"X-User-Id": "u-1"})

    assert response.status_code == 200
    assert response.json()[0]["content"] == "用户偏好先看翠屏湖站点。"
    db_mock.list_memory_items.assert_awaited_once()


def test_user_memory_endpoint_lists_only_current_user_namespace():
    db_mock = _build_db_mock()
    db_mock.list_memory_items = AsyncMock(return_value=[
        {
            "id": 8,
            "namespace": "user:u-1:flood_assistant",
            "item_type": "fact",
            "content": "用户关注北闸站。",
            "importance": 0.7,
            "confidence": 0.8,
            "metadata": {},
            "source_session_id": "session-002",
            "updated_at": "2026-05-02T00:00:00+00:00",
        }
    ])
    with _patched_client(db_mock=db_mock) as (client, _db_mock, _session_mock, _graph):
        response = client.get("/api/v1/memory/user", headers={"X-User-Id": "u-1"})

    assert response.status_code == 200
    assert response.json()[0]["namespace"] == "user:u-1:flood_assistant"
    db_mock.list_memory_items.assert_awaited_once()
    assert db_mock.list_memory_items.await_args.kwargs["namespaces"] == ["user:u-1:flood_assistant"]


def test_memory_endpoint_updates_visible_memory():
    db_mock = _build_db_mock()
    db_mock.update_memory_item = AsyncMock(return_value={
        "id": 7,
        "namespace": "user:u-1:flood_assistant",
        "item_type": "preference",
        "content": "用户偏好先看北闸站。",
        "importance": 0.9,
        "confidence": 0.9,
        "metadata": {"reason": "manual_correction"},
        "source_session_id": "session-001",
        "updated_at": "2026-05-02T00:00:00+00:00",
    })
    with _patched_client(db_mock=db_mock) as (client, _db_mock, _session_mock, _graph):
        response = client.patch(
            "/api/v1/memory/7?session_id=session-001",
            headers={"X-User-Id": "u-1"},
            json={"content": "用户偏好先看北闸站。", "importance": 0.9, "metadata": {"reason": "manual_correction"}},
        )

    assert response.status_code == 200
    assert response.json()["content"] == "用户偏好先看北闸站。"
    db_mock.update_memory_item.assert_awaited_once()
    assert db_mock.update_memory_item.await_args.kwargs["content"] == "用户偏好先看北闸站。"


def test_memory_endpoint_deletes_visible_memory():
    db_mock = _build_db_mock()
    with _patched_client(db_mock=db_mock) as (client, _db_mock, _session_mock, _graph):
        response = client.delete("/api/v1/memory/7?session_id=session-001", headers={"X-User-Id": "u-1"})

    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    db_mock.delete_memory_item.assert_awaited_once()


def test_flood_query_non_stream_returns_503_on_memory_load_failed():
    """Non-stream ``/api/v1/flood/query`` must mirror the SSE endpoint's Req 4.4
    contract.

    Before the fix, when ``memory_loader_node`` short-circuited the graph
    (setting ``error="memory_load_failed: <source>"`` and ``next_agent=__end__``),
    the non-stream handler still ran to completion via the unconditional
    ``memory_loader → supervisor`` edge and persisted a fabricated
    ``response_content = final_state.get("final_response") or "处理完成"`` back
    into ``conversation_messages`` with ``status="completed"``. That created a
    misleading audit trail: the user would see "处理完成" saved as an assistant
    reply to a question the agent never actually handled.

    After the fix, the handler must:
      * NOT persist an assistant message (the user message is kept);
      * NOT trigger ``_persist_result`` (no plan exists);
      * return HTTP 503 with a Chinese ``detail`` so clients can surface a
        retry-friendly error instead of a generic 500.
    """
    # The StubGraph.ainvoke returns this final_state directly, emulating the
    # post-fix graph behaviour where memory_loader short-circuits via the
    # conditional edge and nothing downstream runs.
    graph = StubGraph(final_state={
        "error": "memory_load_failed: conversation_messages",
        "next_agent": "__end__",
        "memory_context": {},
        "current_agent": "memory_loader",
    })

    with _patched_client(graph=graph) as (client, db_mock, session_mock, _graph):
        response = client.post(
            "/api/v1/flood/query",
            json={"query": "继续刚才的问题", "session_id": "session-mem-fail"},
        )

    assert response.status_code == 503
    assert "会话历史加载失败" in response.json()["detail"]

    # The graph was actually invoked — the error came from its final state, not
    # from an exception. If we were incorrectly raising 500 via ``except``
    # branch, ainvoke would still be called, so this primarily guards the
    # post-invoke branch.
    graph.ainvoke.assert_awaited_once()

    # Req (audit trail): the user message must still be persisted — the user
    # asked something, and we want that recorded. But the assistant reply must
    # NOT be persisted as a fabricated success.
    assert db_mock.save_conversation_message.await_count == 1
    (await_args,) = db_mock.save_conversation_message.await_args_list
    assert await_args.args[1] == "user"  # role is the 2nd positional arg
    assert await_args.args[2] == "继续刚才的问题"
    assert await_args.kwargs.get("status") == "completed"

    # No assistant-side persistence happened.
    db_mock.save_emergency_plan.assert_not_awaited()
    db_mock.save_resource_allocations.assert_not_awaited()
    db_mock.save_notifications.assert_not_awaited()
    db_mock.save_conversation_snapshot.assert_not_awaited()

    # Short-term memory only recorded the user turn, never an assistant turn
    # (the 503 short-circuit happens before the assistant save_turn call).
    assistant_turns = [
        call for call in session_mock.save_turn.await_args_list
        if call.args[1] == "assistant"
    ]
    assert assistant_turns == []
