"""FastAPI application entry point backed by LangGraph."""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.database import get_db_service
from app.models import (
    FloodQueryRequest,
    FloodQueryResponse,
    HealthResponse,
    PlanDetailResponse,
    PlanExecuteRequest,
    PlanExecuteResponse,
    SessionResponse,
)
from app.graph import flood_response_graph
from app.services import session as session_service
from app.services.platform_client import get_platform_client
from app.state import RiskAssessment, to_plain_data

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────


async def _persist_result(session_id: str, graph_state: dict) -> None:
    plan = graph_state.get("emergency_plan")
    if not plan:
        return
    db = get_db_service()
    try:
        await db.save_emergency_plan(
            plan_id=plan.plan_id,
            plan_name=plan.plan_name or "防汛应急预案",
            risk_level=_risk_level_value(graph_state.get("risk_assessment")),
            trigger_conditions=plan.trigger_conditions,
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
        logger.warning("[%s] persist failed (non-fatal): %s", session_id, exc)


def _risk_level_value(assessment: RiskAssessment | None) -> str:
    if not assessment:
        return "none"
    return assessment.risk_level.value


def _build_initial_state(session_id: str, query: str, history: list[dict]) -> dict:
    return {
        "session_id": session_id,
        "user_query": query,
        "messages": history + [{"role": "user", "content": query}],
        "iteration": 0,
    }


def _event_line(payload: dict) -> str:
    import json

    return f"data: {json.dumps(to_plain_data(payload), ensure_ascii=False)}\n\n"


def _message_content(update: dict) -> str | None:
    messages = update.get("messages") or []
    if not messages:
        return None
    last = messages[-1]
    if isinstance(last, dict):
        return last.get("content")
    return getattr(last, "content", None)


def _build_stream_events(agent: str, update: dict) -> list[dict]:
    events: list[dict] = [{"type": "agent_update", "agent": agent, "status": "active"}]

    content = _message_content(update)
    if content:
        events.append({"type": "agent_message", "agent": agent, "content": content})

    if update.get("risk_assessment"):
        assessment = update["risk_assessment"]
        events.append({
            "type": "risk_update",
            "level": assessment.risk_level.value,
            "details": assessment.key_risks,
        })

    if update.get("emergency_plan"):
        plan = update["emergency_plan"]
        events.append({
            "type": "plan_update",
            "name": plan.plan_name,
            "status": plan.status,
            "total": len(plan.actions),
            "completed": sum(1 for action in plan.actions if action.status == "completed"),
            "failed": sum(1 for action in plan.actions if action.status == "failed"),
        })

    if update.get("final_response"):
        events.append({
            "type": "agent_message",
            "agent": "final_response",
            "content": update["final_response"],
            "response": update["final_response"],
        })

    events.append({"type": "agent_update", "agent": agent, "status": "done"})
    return events


async def _do_execute_plan(plan_id: str, actions: list[dict]) -> None:
    db = get_db_service()
    platform = get_platform_client()
    failed = 0
    for action in actions:
        action_id = action.get("action_id", "")
        try:
            await db.update_action_status(plan_id, action_id, "in_progress")
            if action.get("action_type") == "notification":
                try:
                    for alarm in (await db.get_active_alarms())[:10]:
                        await platform.acknowledge_alarm(str(alarm["id"]))
                except Exception as exc:
                    logger.warning("[%s] alarm ack failed: %s", plan_id, exc)
            await db.update_action_status(plan_id, action_id, "completed")
        except Exception as exc:
            logger.warning("[%s] action %s failed: %s", plan_id, action_id, exc)
            try:
                await db.update_action_status(plan_id, action_id, "failed")
            except Exception:
                pass
            failed += 1
    await db.update_plan_status(plan_id, "completed" if failed == 0 else "executing")


# ── lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("启动水务AI多 Agent 应急服务")
    db = get_db_service()
    sessions = session_service.get_session_service()
    try:
        await db._get_pool()
        await db.ensure_plan_tables()
        logger.info("数据库连接池就绪")
    except Exception as exc:
        logger.warning("数据库预热失败（服务仍可启动）: %s", exc)
    yield
    await db.close()
    await sessions.close()
    await get_platform_client().close()
    logger.info("水务AI多 Agent 应急服务已关闭")


# ── app ───────────────────────────────────────────────────────────────────────


app = FastAPI(
    title="水务AI防洪应急服务（多 Agent）",
    description="基于 LangGraph 的多 Agent 防洪应急与指挥辅助服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse()


@app.post("/api/v1/flood/query", response_model=FloodQueryResponse)
async def flood_query(request: FloodQueryRequest) -> FloodQueryResponse:
    session_id = request.session_id or str(uuid.uuid4())
    logger.info("[%s] flood query: %s", session_id, request.query[:80])
    sessions = session_service.get_session_service()
    history = await sessions.get_history(session_id)
    await sessions.save_turn(session_id, "user", request.query)

    try:
        final_state = await flood_response_graph.ainvoke(_build_initial_state(session_id, request.query, history))
    except Exception as exc:
        logger.exception("[%s] graph failed: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=f"处理失败: {exc}") from exc

    await sessions.save_turn(session_id, "assistant", final_state.get("final_response") or "处理完成")
    await _persist_result(session_id, final_state)
    assessment = final_state.get("risk_assessment")
    plan = final_state.get("emergency_plan")
    resources = final_state.get("resource_plan", [])
    notifications = final_state.get("notifications", [])
    return FloodQueryResponse(
        session_id=session_id,
        response=final_state.get("final_response") or "处理完成",
        risk_level=_risk_level_value(assessment),
        risk_score=assessment.risk_score if assessment else None,
        plan_id=plan.plan_id if plan else None,
        plan_name=plan.plan_name if plan else None,
        actions_count=len(plan.actions) if plan else 0,
        resources_count=len(resources),
        notifications_count=len(notifications),
    )


@app.post("/api/v1/flood/query/stream")
async def flood_query_stream(request: FloodQueryRequest):
    session_id = request.session_id or str(uuid.uuid4())
    sessions = session_service.get_session_service()

    async def event_stream():
        history = await sessions.get_history(session_id)
        await sessions.save_turn(session_id, "user", request.query)
        final_state = None
        try:
            yield _event_line({"type": "session_init", "sessionId": session_id})
            async for update in flood_response_graph.astream(
                _build_initial_state(session_id, request.query, history),
                stream_mode="updates",
            ):
                node_name, node_update = next(iter(update.items()))
                final_state = {**(final_state or {}), **node_update}
                for event in _build_stream_events(node_name, node_update):
                    yield _event_line(event)
            if final_state:
                await sessions.save_turn(session_id, "assistant", final_state.get("final_response") or "处理完成")
                await _persist_result(session_id, final_state)
            yield _event_line({"type": "agent_update", "agent": "__done__", "status": "done"})
        except Exception as exc:
            logger.exception("[%s] stream failed: %s", session_id, exc)
            yield _event_line({"type": "agent_update", "agent": "__error__", "status": "failed", "error": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── plan endpoints ────────────────────────────────────────────────────────────


@app.get("/api/v1/plans", response_model=list[dict])
async def list_plans(limit: int = 20, offset: int = 0):
    try:
        return await get_db_service().get_plans(limit, offset)
    except Exception as exc:
        logger.exception("list plans: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/plans/count")
async def get_plan_count():
    try:
        return {"count": await get_db_service().get_plan_count()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/plans/{plan_id}", response_model=PlanDetailResponse)
async def get_plan(plan_id: str):
    try:
        db = get_db_service()
        plan = await db.get_emergency_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="预案不存在")
        return PlanDetailResponse(
            plan_id=plan["plan_id"],
            plan_name=plan["plan_name"],
            risk_level=plan["risk_level"],
            trigger_conditions=plan["trigger_conditions"],
            status=plan["status"],
            session_id=plan["session_id"],
            summary=plan["summary"],
            actions=await db.get_plan_actions(plan_id),
            resources=await db.get_plan_resources(plan_id),
            notifications=await db.get_plan_notifications(plan_id),
            created_at=str(plan["created_at"]) if plan.get("created_at") else None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get plan %s: %s", plan_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/plans/{plan_id}/execute", response_model=PlanExecuteResponse)
async def execute_plan(plan_id: str, background_tasks: BackgroundTasks, request: PlanExecuteRequest | None = None):
    try:
        db = get_db_service()
        plan = await db.get_emergency_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="预案不存在")
        actions = await db.get_plan_actions(plan_id)
        if request and request.action_ids:
            actions = [a for a in actions if a.get("action_id") in request.action_ids]
        await db.update_plan_status(plan_id, "executing")
        background_tasks.add_task(_do_execute_plan, plan_id, actions)
        return PlanExecuteResponse(
            plan_id=plan_id,
            status="executing",
            executed_actions=len(actions),
            message=f"预案已开始执行，共 {len(actions)} 项措施",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("execute plan %s: %s", plan_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/api/v1/plans/{plan_id}/status")
async def update_plan_status_endpoint(plan_id: str, body: dict):
    valid_statuses = {"draft", "approved", "executing", "completed"}
    status = body.get("status", "")
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效状态，有效值: {sorted(valid_statuses)}")
    db = get_db_service()
    if not await db.get_emergency_plan(plan_id):
        raise HTTPException(status_code=404, detail="预案不存在")
    await db.update_plan_status(plan_id, status)
    return {"plan_id": plan_id, "status": status}


@app.delete("/api/v1/plans/{plan_id}")
async def delete_plan(plan_id: str):
    db = get_db_service()
    if not await db.get_emergency_plan(plan_id):
        raise HTTPException(status_code=404, detail="预案不存在")
    try:
        pool = await db._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM emergency_plan WHERE plan_id = $1", plan_id)
        return {"message": "预案已删除"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── session endpoints ─────────────────────────────────────────────────────────


@app.get("/api/v1/sessions", response_model=list[dict])
async def list_sessions(limit: int = 20, offset: int = 0):
    try:
        return await get_db_service().get_sessions(limit, offset)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/sessions/count")
async def get_session_count():
    try:
        return {"count": await get_db_service().get_session_count()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    try:
        plans = await get_db_service().get_plans_by_session(session_id)
        if not plans:
            raise HTTPException(status_code=404, detail="会话不存在")
        created_at = plans[0].get("created_at") if plans else None
        return SessionResponse(
            session_id=session_id,
            plans=plans,
            created_at=str(created_at) if created_at else None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
