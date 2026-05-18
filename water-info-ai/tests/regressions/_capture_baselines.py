"""One-shot baseline-fixture generator for Task 2.1.

This is a helper module — **not** a pytest test file. It is intentionally
prefixed with ``_`` so pytest does not auto-collect it. To regenerate the
three ``sse_baseline_<scenario>.json`` fixtures, run::

    cd water-info-ai
    uv run python -m tests.regressions._capture_baselines

The script drives the FastAPI app with a hand-crafted ``StubGraph`` per
scenario (the same pattern used by ``tests/test_main_api.py``) so the
captured SSE stream is deterministic and reproducible. With all five
``supervisor-autogen-enhancements`` flags off (the default), the stub graph's
output is the byte-for-byte baseline that Task 2.2's Property 4 test will
diff against.

Why a stub graph instead of the full pipeline?
----------------------------------------------

Running the real ``flood_response_graph`` end-to-end requires a real
Postgres pool, the embedding client, the platform client, and a real LLM —
none of which are available deterministically in the test environment. The
existing test suite already uses ``StubGraph`` (see ``test_main_api.py``)
for the same reason; we mirror that constraint here. The conftest header
documents the audit-row gap this introduces.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

# Force every supervisor-autogen-enhancements flag off before importing the
# app. ``get_settings`` is ``lru_cache``d, so this must precede the import.
for _env_key in (
    "OTEL_ENABLED",
    "AGENT_CONTRACTS_ENABLED",
    "DYNAMIC_TOPOLOGY_ENABLED",
    "HITL_ENABLED",
    "LANGGRAPH_POSTGRES_ENABLED",
    "AUDIT_TABLES_ENABLED",
):
    os.environ[_env_key] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.state import (  # noqa: E402
    EmergencyAction,
    EmergencyPlan,
    NotificationRecord,
    ResourceAllocation,
    RiskAssessment,
    RiskLevel,
)
from tests.regressions.conftest import (  # noqa: E402
    FIXTURES_DIR,
    SCENARIOS,
    BaselineRecorder,
)

# ── StubGraph ────────────────────────────────────────────────────────────────


class StubGraph:
    """Minimal stand-in for a compiled LangGraph graph.

    Mirrors the surface used by ``app.main``:

    * ``ainvoke(state, config)`` — returns ``final_state`` directly.
    * ``astream(state, config, stream_mode="updates")`` — async-iterates the
      pre-computed ``stream_events`` so the SSE handler sees one
      ``{node_name: node_update}`` dict per ``await``.
    """

    def __init__(
        self,
        *,
        final_state: dict[str, Any] | None = None,
        stream_events: list[dict[str, Any]] | None = None,
    ) -> None:
        self.ainvoke = AsyncMock(return_value=final_state or {})
        self._stream_events = list(stream_events or [])

    async def astream(self, *_args: Any, **_kwargs: Any):
        for event in self._stream_events:
            yield event


# ── DB / session stubs (no IO) ────────────────────────────────────────────────


def _build_db_mock() -> SimpleNamespace:
    """Database stub matching the shape used in ``tests/test_main_api.py``.

    ``save_conversation_message`` returns a deterministic ID per call so the
    SSE handler's two writes (user, assistant placeholder) are stable.
    """
    return SimpleNamespace(
        _get_pool=AsyncMock(return_value=object()),
        ensure_plan_tables=AsyncMock(),
        ensure_conversation_tables=AsyncMock(),
        ensure_kb_tables=AsyncMock(),
        close=AsyncMock(),
        ensure_or_create_session=AsyncMock(),
        save_conversation_message=AsyncMock(side_effect=[1001, 1002, 1003, 1004]),
        update_message_content=AsyncMock(),
        get_conversation_messages=AsyncMock(return_value=[]),
        save_conversation_snapshot=AsyncMock(),
        save_emergency_plan=AsyncMock(),
        save_resource_allocations=AsyncMock(),
        save_notifications=AsyncMock(),
    )


def _build_session_mock() -> SimpleNamespace:
    return SimpleNamespace(
        get_history=AsyncMock(return_value=[]),
        save_turn=AsyncMock(),
        close=AsyncMock(),
    )


# ── Scenario builders ─────────────────────────────────────────────────────────


def _general_chat_stream_events() -> list[dict[str, Any]]:
    """``conversation_assistant`` only; no risk / plan / resources."""
    reply = (
        "你好，我是防汛 AI 助手。\n\n"
        "我可以陪你一起看站点状态、研判风险、生成预案，也可以先回答你想了解的内容。"
        "如果你愿意，我们可以从某个站点、某段河道，或者当前整体水情开始。"
    )
    return [
        {
            "memory_loader": {
                "current_agent": "memory_loader",
                "memory_context": {},
            }
        },
        {
            "supervisor": {
                "next_agent": "conversation_assistant",
                "iteration": 1,
                "current_agent": "supervisor",
                "intent": "general_chat",
                "supervisor_reasoning": "general chat hard route",
                "execution_traces": [
                    {
                        "phase": "data_query",
                        "status": "completed",
                        "title": "意图识别: general_chat",
                        "detail": "",
                        "tool_name": None,
                        "metadata": {},
                    }
                ],
            }
        },
        {
            "conversation_assistant": {
                "current_agent": "conversation_assistant",
                "final_response_draft": reply,
                "messages": [{"role": "conversation_assistant", "content": reply}],
            }
        },
        {
            "final_response": {
                "current_agent": "final_response",
                "final_response": reply,
                "messages": [{"role": "final_response", "content": reply}],
                "execution_traces": [
                    {
                        "phase": "final_response",
                        "status": "completed",
                        "title": "最终回答生成",
                        "detail": "",
                        "tool_name": None,
                        "metadata": {},
                    }
                ],
            }
        },
        {
            "memory_writer": {
                "current_agent": "memory_writer",
                "memory_write_result": {"saved": 0, "skipped": "no_candidates"},
            }
        },
    ]


def _data_only_stream_events() -> list[dict[str, Any]]:
    """``answer_policy.data_only=True`` — runs through ``data_analyst`` only."""
    summary = (
        "北闸站 最新 1 条水位数据\n\n"
        "| 时间 | 指标 | 数值 | 单位 | 质量 |\n"
        "| --- | --- | ---: | --- | --- |\n"
        "| 2026-05-10T08:00:00+00:00 | 水位 | 4.248 | m | OK |"
    )
    return [
        {
            "memory_loader": {
                "current_agent": "memory_loader",
                "memory_context": {},
            }
        },
        {
            "supervisor": {
                "next_agent": "data_analyst",
                "iteration": 1,
                "current_agent": "supervisor",
                "intent": "station_status",
                "answer_policy": {
                    "data_only": True,
                    "data_lookup": True,
                    "requested_count": 1,
                    "metric_type": "WATER_LEVEL",
                    "suppress_risk": True,
                    "suppress_summary": True,
                },
                "supervisor_reasoning": "data-only lookup",
                "execution_traces": [
                    {
                        "phase": "data_query",
                        "status": "completed",
                        "title": "意图识别: station_status",
                        "detail": "焦点站点: 北闸站",
                        "tool_name": None,
                        "metadata": {},
                    },
                    {
                        "phase": "data_query",
                        "status": "completed",
                        "title": "检测到纯数据查询，跳过风险评估",
                        "detail": "",
                        "tool_name": None,
                        "metadata": {},
                    },
                ],
            }
        },
        {
            "data_analyst": {
                "current_agent": "data_analyst",
                "data_summary": summary,
                "messages": [{"role": "data_analyst", "content": summary}],
                "execution_traces": [
                    {
                        "phase": "tool_call",
                        "status": "completed",
                        "title": "查询北闸站最新观测数据",
                        "detail": "",
                        "tool_name": "get_recent_observations",
                        "metadata": {
                            "duration_ms": 18,
                            "input_summary": "station_id=BZ-01, metric_type=WATER_LEVEL, limit=1",
                            "output_summary": "获取到 1 条水位观测记录",
                        },
                    }
                ],
            }
        },
        {
            "supervisor": {
                "next_agent": "__end__",
                "iteration": 2,
                "current_agent": "supervisor",
                "intent": "station_status",
                "supervisor_reasoning": "deterministic complete (data_only)",
                "execution_traces": [
                    {
                        "phase": "data_query",
                        "status": "completed",
                        "title": "意图识别: station_status",
                        "detail": "",
                        "tool_name": None,
                        "metadata": {},
                    }
                ],
            }
        },
        {
            "final_response": {
                "current_agent": "final_response",
                "final_response": summary,
                "messages": [{"role": "final_response", "content": summary}],
                "execution_traces": [
                    {
                        "phase": "final_response",
                        "status": "completed",
                        "title": "最终回答生成",
                        "detail": "",
                        "tool_name": None,
                        "metadata": {},
                    }
                ],
            }
        },
        {
            "memory_writer": {
                "current_agent": "memory_writer",
                "memory_write_result": {"saved": 0, "skipped": "no_candidates"},
            }
        },
    ]


def _full_workflow_stream_events() -> list[dict[str, Any]]:
    """Flood emergency: data_analyst → risk_assessor → plan_generator →
    resource_dispatcher → notification → final_response. No CRITICAL safety.
    """
    plan = EmergencyPlan(
        plan_id="EP-REGRESSION-001",
        plan_name="城区防汛响应预案",
        risk_level=RiskLevel.HIGH,
        trigger_conditions="北闸站水位逼近警戒线",
        actions=[
            EmergencyAction(
                action_id="A-001",
                action_type="patrol",
                description="加密重点河段巡查",
                priority=1,
                responsible_dept="防汛办",
                deadline_minutes=30,
            ),
            EmergencyAction(
                action_id="A-002",
                action_type="notification",
                description="通知沿线街道",
                priority=2,
                responsible_dept="应急办",
                deadline_minutes=15,
            ),
        ],
        summary="启动高风险响应。",
    )
    return [
        {
            "memory_loader": {
                "current_agent": "memory_loader",
                "memory_context": {},
            }
        },
        {
            "supervisor": {
                "next_agent": "data_analyst",
                "iteration": 1,
                "current_agent": "supervisor",
                "intent": "plan_generation",
                "supervisor_reasoning": "plan generation requested",
                "execution_traces": [
                    {
                        "phase": "data_query",
                        "status": "completed",
                        "title": "意图识别: plan_generation",
                        "detail": "",
                        "tool_name": None,
                        "metadata": {},
                    }
                ],
            }
        },
        {
            "data_analyst": {
                "current_agent": "data_analyst",
                "data_summary": "北闸站水位接近警戒线，区域降雨持续。",
                "messages": [
                    {"role": "data_analyst", "content": "已完成数据分析"}
                ],
                "execution_traces": [
                    {
                        "phase": "tool_call",
                        "status": "completed",
                        "title": "获取全局水情概览",
                        "detail": "",
                        "tool_name": "get_flood_situation_overview",
                        "metadata": {
                            "duration_ms": 24,
                            "input_summary": "",
                            "output_summary": "5 个站点, 2 条告警",
                        },
                    }
                ],
            }
        },
        {
            "supervisor": {
                "next_agent": "risk_assessor",
                "iteration": 2,
                "current_agent": "supervisor",
                "supervisor_reasoning": "advance to risk assessment",
                "execution_traces": [
                    {
                        "phase": "data_query",
                        "status": "completed",
                        "title": "意图识别: plan_generation",
                        "detail": "",
                        "tool_name": None,
                        "metadata": {},
                    }
                ],
            }
        },
        {
            "risk_assessor": {
                "current_agent": "risk_assessor",
                "risk_assessment": RiskAssessment(
                    risk_level=RiskLevel.HIGH,
                    risk_score=72.0,
                    affected_stations=["BZ-01"],
                    key_risks=["北闸站水位接近警戒线", "未来 24 小时仍有降雨"],
                    trend="rising",
                    reasoning="基于监测站水位、雨量和活跃告警的综合评分",
                    response_level="III",
                ),
                "messages": [
                    {"role": "risk_assessor", "content": "风险等级: high (72.0)"}
                ],
                "execution_traces": [
                    {
                        "phase": "risk_assessment",
                        "status": "completed",
                        "title": "风险评估完成",
                        "detail": "综合评分 72.0",
                        "tool_name": None,
                        "metadata": {"duration_ms": 12},
                    }
                ],
            }
        },
        {
            "supervisor": {
                "next_agent": "plan_generator",
                "iteration": 3,
                "current_agent": "supervisor",
                "supervisor_reasoning": "advance to plan generation",
                "execution_traces": [
                    {
                        "phase": "data_query",
                        "status": "completed",
                        "title": "意图识别: plan_generation",
                        "detail": "",
                        "tool_name": None,
                        "metadata": {},
                    }
                ],
            }
        },
        {
            "plan_generator": {
                "current_agent": "plan_generator",
                "emergency_plan": plan,
                "messages": [
                    {"role": "plan_generator", "content": "已生成预案 城区防汛响应预案"}
                ],
                "execution_traces": [
                    {
                        "phase": "plan_generation",
                        "status": "completed",
                        "title": "预案生成完成",
                        "detail": "2 项措施",
                        "tool_name": None,
                        "metadata": {"duration_ms": 18},
                    }
                ],
            }
        },
        {
            "supervisor": {
                "next_agent": "resource_dispatcher",
                "iteration": 4,
                "current_agent": "supervisor",
                "supervisor_reasoning": "advance to resource dispatch",
                "execution_traces": [
                    {
                        "phase": "data_query",
                        "status": "completed",
                        "title": "意图识别: plan_generation",
                        "detail": "",
                        "tool_name": None,
                        "metadata": {},
                    }
                ],
            }
        },
        {
            "resource_dispatcher": {
                "current_agent": "resource_dispatcher",
                "resource_plan": [
                    ResourceAllocation(
                        resource_type="人员",
                        resource_name="抢险队",
                        quantity=12,
                        source_location="市级应急仓库",
                        target_location="城区河段",
                        eta_minutes=30,
                    )
                ],
                "messages": [
                    {"role": "resource_dispatcher", "content": "已制定 1 项资源调度安排"}
                ],
                "execution_traces": [
                    {
                        "phase": "resource_dispatch",
                        "status": "completed",
                        "title": "资源调度完成: 1 项",
                        "detail": "",
                        "tool_name": None,
                        "metadata": {"duration_ms": 9},
                    }
                ],
            }
        },
        {
            "supervisor": {
                "next_agent": "notification",
                "iteration": 5,
                "current_agent": "supervisor",
                "supervisor_reasoning": "advance to notification",
                "execution_traces": [
                    {
                        "phase": "data_query",
                        "status": "completed",
                        "title": "意图识别: plan_generation",
                        "detail": "",
                        "tool_name": None,
                        "metadata": {},
                    }
                ],
            }
        },
        {
            "notification": {
                "current_agent": "notification",
                "notifications": [
                    NotificationRecord(
                        target="应急办",
                        channel="sms",
                        content="请立即进入防汛待命状态。",
                    )
                ],
                "messages": [
                    {"role": "notification", "content": "已生成 1 条通知"}
                ],
            }
        },
        {
            "supervisor": {
                "next_agent": "__end__",
                "iteration": 6,
                "current_agent": "supervisor",
                "supervisor_reasoning": "deterministic complete",
                "execution_traces": [
                    {
                        "phase": "final_response",
                        "status": "completed",
                        "title": "工作流完成，准备生成最终回答",
                        "detail": "",
                        "tool_name": None,
                        "metadata": {},
                    }
                ],
            }
        },
        {
            "final_response": {
                "current_agent": "final_response",
                "final_response": (
                    "综合研判：风险等级: high。\n\n"
                    "已生成预案 城区防汛响应预案，包含 2 项措施、1 项资源调度、1 条通知。"
                ),
                "messages": [
                    {
                        "role": "final_response",
                        "content": (
                            "综合研判：风险等级: high。\n\n"
                            "已生成预案 城区防汛响应预案，包含 2 项措施、1 项资源调度、1 条通知。"
                        ),
                    }
                ],
                "execution_traces": [
                    {
                        "phase": "final_response",
                        "status": "completed",
                        "title": "最终回答生成",
                        "detail": "",
                        "tool_name": None,
                        "metadata": {},
                    }
                ],
            }
        },
        {
            "memory_writer": {
                "current_agent": "memory_writer",
                "memory_write_result": {"saved": 0, "skipped": "no_candidates"},
            }
        },
    ]


_SCENARIO_BUILDERS: dict[str, dict[str, Any]] = {
    "general_chat": {
        "query": "你好",
        "session_id": "regression-general-chat",
        "stream_events": _general_chat_stream_events,
    },
    "data_only": {
        "query": "查一下北闸站最新水位，无需分析",
        "session_id": "regression-data-only",
        "stream_events": _data_only_stream_events,
    },
    "full_workflow": {
        "query": "请生成城区防汛应急响应预案",
        "session_id": "regression-full-workflow",
        "stream_events": _full_workflow_stream_events,
    },
}


# ── Capture machinery ─────────────────────────────────────────────────────────


def _capture_one(scenario: str, *, regenerate: bool) -> dict[str, Any]:
    """Drive the SSE endpoint once for ``scenario`` and write the fixture."""
    config = _SCENARIO_BUILDERS[scenario]
    db_mock = _build_db_mock()
    session_mock = _build_session_mock()
    graph = StubGraph(stream_events=config["stream_events"]())

    with ExitStack() as stack:
        stack.enter_context(patch("app.main.get_db_service", return_value=db_mock))
        stack.enter_context(patch("app.main.flood_response_graph", graph))
        stack.enter_context(
            patch("app.services.session.get_session_service", return_value=session_mock)
        )
        client = stack.enter_context(TestClient(app))
        with client.stream(
            "POST",
            "/api/v1/flood/query/stream",
            json={"query": config["query"], "session_id": config["session_id"]},
        ) as response:
            assert response.status_code == 200, response.read()
            body = "".join(response.iter_text())

    # Pull the metadata payload that the SSE handler wrote at the end of the
    # stream. ``update_message_content`` is awaited at most once per stream
    # (the assistant placeholder gets either ``status="completed"`` with a
    # full metadata dict, or ``status="failed"`` with no metadata).
    message_metadata: dict[str, Any] = {}
    if db_mock.update_message_content.await_args is not None:
        message_metadata = (
            db_mock.update_message_content.await_args.kwargs.get("metadata") or {}
        )

    recorder = BaselineRecorder(scenario=scenario, regenerate=regenerate)
    recorder.record(
        sse_body=body,
        message_metadata=message_metadata,
        audit_rows=[],
    )
    return recorder.finalize()


def main(*, regenerate: bool = True) -> None:
    """Capture all three baseline fixtures.

    Defaults to ``regenerate=True`` — the only reason to run this module is
    to (re)write the on-disk fixture files. Pass ``regenerate=False`` to do
    a dry-run sanity check (useful from inside another test harness).
    """
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for scenario in SCENARIOS:
        captured = _capture_one(scenario, regenerate=regenerate)
        path = Path(FIXTURES_DIR) / f"sse_baseline_{scenario}.json"
        record_count = len(captured["sse_records"])
        print(f"  {scenario}: {record_count} SSE records → {path}")


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    print("Capturing supervisor-autogen-enhancements baseline fixtures …")
    main(regenerate=True)
    print("done.")
