"""FastAPI application entry point."""

from __future__ import annotations

import json
import logging
import uuid
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
from app.pipeline import FloodPipeline
from app.platform_client import get_platform_client

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────


async def _persist_result(session_id: str, pipeline: FloodPipeline) -> None:
    r = pipeline.result
    if not r.plan_id:
        return
    db = get_db_service()
    try:
        await db.save_emergency_plan(
            plan_id=r.plan_id,
            plan_name=r.plan_name or "防汛应急预案",
            risk_level=r.risk_level or "none",
            trigger_conditions="",
            status="draft",
            session_id=session_id,
            summary=r.response[:2000],
            actions=r.actions,
        )
        if r.resources:
            await db.save_resource_allocations(r.plan_id, r.resources)
        if r.notifications:
            await db.save_notifications(r.plan_id, r.notifications)
    except Exception as exc:
        logger.warning("[%s] persist failed (non-fatal): %s", session_id, exc)


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
    logger.info("启动水务AI轻量应急服务")
    db = get_db_service()
    try:
        await db._get_pool()
        await db.ensure_plan_tables()
        logger.info("数据库连接池就绪")
    except Exception as exc:
        logger.warning("数据库预热失败（服务仍可启动）: %s", exc)
    yield
    await db.close()
    await get_platform_client().close()
    logger.info("水务AI轻量应急服务已关闭")


# ── app ───────────────────────────────────────────────────────────────────────


app = FastAPI(
    title="水务AI防洪应急服务（轻量版）",
    description="基于顺序流水线的防洪应急预案生成服务，无 LangGraph/LangChain 依赖",
    version="1.0.0",
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

    pipeline = FloodPipeline(request.query, session_id)
    try:
        # Consume the full pipeline (non-streaming)
        async for _ in pipeline.run():
            pass
    except Exception as exc:
        logger.exception("[%s] pipeline failed: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=f"处理失败: {exc}") from exc

    await _persist_result(session_id, pipeline)
    r = pipeline.result
    return FloodQueryResponse(
        session_id=session_id,
        response=r.response or "处理完成",
        risk_level=r.risk_level,
        risk_score=r.risk_score,
        plan_id=r.plan_id,
        plan_name=r.plan_name,
        actions_count=len(r.actions),
        resources_count=len(r.resources),
        notifications_count=len(r.notifications),
    )


@app.post("/api/v1/flood/query/stream")
async def flood_query_stream(request: FloodQueryRequest):
    session_id = request.session_id or str(uuid.uuid4())
    pipeline = FloodPipeline(request.query, session_id)

    async def event_stream():
        try:
            async for chunk in pipeline.run():
                yield chunk
            await _persist_result(session_id, pipeline)
        except Exception as exc:
            logger.exception("[%s] stream failed: %s", session_id, exc)
            yield f"data: {json.dumps({'type': 'agent_update', 'agent': '__error__', 'status': 'failed', 'error': str(exc)}, ensure_ascii=False)}\n\n"

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
