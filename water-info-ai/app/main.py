"""FastAPI application entry point backed by LangGraph."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import asdict
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.database import get_db_service
from app.models import (
    ConversationDetailResponse,
    ConversationFullResponse,
    ConversationItem,
    ConversationMessage,
    ConversationSession,
    ConversationSnapshot,
    CreateConversationResponse,
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
from app.services.llm import get_llm
from app.services.platform_client import get_platform_client
from app.state import RiskAssessment, to_plain_data

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Header names for user identity forwarding
HEADER_USER_ID = "X-User-Id"
HEADER_USERNAME = "X-Username"


def _get_user_from_request(request: Request) -> tuple[str, str]:
    """Extract user identity from request headers."""
    user_id = request.headers.get(HEADER_USER_ID, "")
    username = request.headers.get(HEADER_USERNAME, "")
    return user_id, username


# ── helpers ───────────────────────────────────────────────────────────────────


async def _persist_result(session_id: str, graph_state: dict) -> None:
    """Persist emergency plan and update conversation snapshot."""
    plan = graph_state.get("emergency_plan")
    db = get_db_service()
    
    # Always update snapshot with current state
    assessment = graph_state.get("risk_assessment")
    risk_level = _risk_level_value(assessment)
    plan_info = {}
    if plan:
        plan_info = {
            "plan_id": plan.plan_id,
            "plan_name": plan.plan_name,
            "status": plan.status,
            "actions_count": len(plan.actions) if plan.actions else 0,
        }
    
    try:
        await db.save_conversation_snapshot(
            session_id=session_id,
            risk_level=risk_level,
            plan_info=plan_info if plan else None,
            agent_status_summary={"status": "completed"},
        )
    except Exception as exc:
        logger.warning("[%s] snapshot persist failed: %s", session_id, exc)

    if not plan:
        return
    
    try:
        await db.save_emergency_plan(
            plan_id=plan.plan_id,
            plan_name=plan.plan_name or "防汛应急预案",
            risk_level=risk_level,
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
        logger.warning("[%s] plan persist failed (non-fatal): %s", session_id, exc)


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
    await get_llm().aclose()
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
async def flood_query(request: FloodQueryRequest, http_request: Request) -> FloodQueryResponse:
    """Execute flood emergency query (non-streaming)."""
    user_id, username = _get_user_from_request(http_request)
    is_new_session = not request.session_id
    session_id = request.session_id or str(uuid.uuid4())
    logger.info("[%s] flood query from user=%s: %s", session_id, user_id or "anonymous", request.query[:80])
    
    db = get_db_service()
    sessions = session_service.get_session_service()

    # Auto-create session using first 30 chars of query as title (first message creates session)
    title = request.query[:30] + ("…" if len(request.query) > 30 else "")
    await db.ensure_or_create_session(
        session_id, title, user_id=user_id, username=username, title_source="auto_first_query"
    )

    history = await sessions.get_history(session_id)
    # Save user message with new schema
    await db.save_conversation_message(session_id, "user", request.query, message_type="chat", status="completed")

    try:
        final_state = await flood_response_graph.ainvoke(_build_initial_state(session_id, request.query, history))
    except Exception as exc:
        logger.exception("[%s] graph failed: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=f"处理失败: {exc}") from exc

    # Save assistant response
    response_content = final_state.get("final_response") or "处理完成"
    await db.save_conversation_message(session_id, "assistant", response_content, message_type="chat", status="completed")
    
    # Persist plan and snapshot
    asyncio.create_task(_persist_result(session_id, final_state))
    
    assessment = final_state.get("risk_assessment")
    plan = final_state.get("emergency_plan")
    resources = final_state.get("resource_plan", [])
    notifications = final_state.get("notifications", [])
    return FloodQueryResponse(
        session_id=session_id,
        response=response_content,
        risk_level=_risk_level_value(assessment),
        risk_score=assessment.risk_score if assessment else None,
        plan_id=plan.plan_id if plan else None,
        plan_name=plan.plan_name if plan else None,
        actions_count=len(plan.actions) if plan else 0,
        resources_count=len(resources),
        notifications_count=len(notifications),
    )


@app.post("/api/v1/flood/query/stream")
async def flood_query_stream(request: FloodQueryRequest, http_request: Request):
    """Execute flood emergency query with streaming (SSE)."""
    user_id, username = _get_user_from_request(http_request)
    is_new_session = not request.session_id
    session_id = request.session_id or str(uuid.uuid4())
    db = get_db_service()
    sessions = session_service.get_session_service()

    async def event_stream():
        nonlocal session_id
        title = request.query[:30] + ("…" if len(request.query) > 30 else "")
        
        # Create session with user ownership
        await db.ensure_or_create_session(
            session_id, title, user_id=user_id, username=username, title_source="auto_first_query"
        )
        
        history = await sessions.get_history(session_id)
        
        # Save user message
        await db.save_conversation_message(session_id, "user", request.query, message_type="chat", status="completed")
        
        # Create assistant placeholder message with streaming status
        assistant_msg_id = await db.save_conversation_message(
            session_id, "assistant", "", message_type="chat", status="streaming"
        )
        
        final_state = None
        accumulated_response = ""
        
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
                    # Track final response for persistence
                    if event.get("type") == "agent_message" and event.get("agent") == "final_response":
                        accumulated_response = event.get("response", "")
            
            if final_state:
                final_response = final_state.get("final_response") or accumulated_response or "处理完成"
                # Update assistant message to completed
                await db.update_message_content(assistant_msg_id, final_response, status="completed")
                # Persist plan and snapshot
                asyncio.create_task(_persist_result(session_id, final_state))
            yield _event_line({"type": "agent_update", "agent": "__done__", "status": "done"})
        except Exception as exc:
            logger.exception("[%s] stream failed: %s", session_id, exc)
            # Mark assistant message as failed
            try:
                await db.update_message_content(assistant_msg_id, f"处理失败: {exc}", status="failed")
            except Exception:
                pass
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


# ── conversation endpoints ────────────────────────────────────────────────────


@app.post("/api/v1/conversations", response_model=CreateConversationResponse)
async def create_conversation(http_request: Request, body: dict | None = None):
    """Create a new conversation session (optional - sessions are auto-created on first query)."""
    import uuid as _uuid
    user_id, username = _get_user_from_request(http_request)
    session_id = str(_uuid.uuid4())
    title = ((body or {}).get("title") or "新会话")[:60]
    db = get_db_service()
    await db.ensure_or_create_session(session_id, title, user_id=user_id, username=username, title_source="manual")
    row = await db._fetchrow(
        "SELECT session_id, title, created_at FROM conversation_session WHERE session_id = $1",
        session_id,
    )
    return CreateConversationResponse(
        session_id=session_id,
        title=title,
        created_at=str(row["created_at"]) if row else "",
    )


@app.get("/api/v1/conversations", response_model=list[ConversationItem])
async def list_conversations(http_request: Request, limit: int = 50, offset: int = 0):
    """List conversations for the current user."""
    user_id, _ = _get_user_from_request(http_request)
    try:
        rows = await get_db_service().list_conversations(limit, offset, user_id=user_id if user_id else None)
        return [
            ConversationItem(
                session_id=r["session_id"],
                title=r["title"],
                message_count=int(r["message_count"] or 0),
                last_message=r.get("last_message"),
                status=r.get("status", "active"),
                created_at=str(r["created_at"]) if r.get("created_at") else None,
                updated_at=str(r["updated_at"]) if r.get("updated_at") else None,
            )
            for r in rows
        ]
    except Exception as exc:
        logger.exception("list conversations: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/conversations/{session_id}", response_model=ConversationFullResponse)
async def get_conversation(session_id: str, http_request: Request):
    """Get conversation metadata and snapshot (for session recovery without messages)."""
    user_id, _ = _get_user_from_request(http_request)
    try:
        db = get_db_service()
        # Check ownership if user_id is provided
        session = await db.get_session_by_id(session_id, user_id=user_id if user_id else None)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        snapshot_row = await db.get_conversation_snapshot(session_id)
        snapshot = None
        if snapshot_row:
            snapshot = ConversationSnapshot(
                risk_level=snapshot_row.get("risk_level", "none"),
                plan_info=snapshot_row.get("plan_info"),
                agent_status_summary=snapshot_row.get("agent_status_summary"),
                query_count=snapshot_row.get("query_count", 0),
            )
        
        # Get latest plan summary if any
        plans = await db.get_plans_by_session(session_id)
        latest_plan = plans[0] if plans else None
        
        return ConversationFullResponse(
            session=ConversationSession(
                session_id=session["session_id"],
                title=session["title"],
                status=session.get("status", "active"),
                user_id=session.get("user_id"),
                username=session.get("username"),
                last_message_at=str(session["last_message_at"]) if session.get("last_message_at") else None,
                last_message_preview=session.get("last_message_preview"),
                title_source=session.get("title_source", "auto_first_query"),
                created_at=str(session["created_at"]) if session.get("created_at") else None,
                updated_at=str(session["updated_at"]) if session.get("updated_at") else None,
            ),
            snapshot=snapshot,
            latest_plan_summary=latest_plan,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get conversation %s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/conversations/{session_id}/messages", response_model=ConversationDetailResponse)
async def get_conversation_messages(
    session_id: str,
    http_request: Request,
    limit: int = 40,
    before_id: int | None = None,
):
    """Get messages for a conversation with cursor-based pagination."""
    user_id, _ = _get_user_from_request(http_request)
    try:
        db = get_db_service()
        # Check ownership if user_id is provided
        session = await db.get_session_by_id(session_id, user_id=user_id if user_id else None)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        msgs = await db.get_conversation_messages(session_id, limit=limit + 1, before_id=before_id)
        has_more = len(msgs) > limit
        if has_more:
            msgs = msgs[1:]  # Remove the extra item used for pagination check
        
        snapshot_row = await db.get_conversation_snapshot(session_id)
        snapshot = None
        if snapshot_row:
            snapshot = ConversationSnapshot(
                risk_level=snapshot_row.get("risk_level", "none"),
                plan_info=snapshot_row.get("plan_info"),
                agent_status_summary=snapshot_row.get("agent_status_summary"),
                query_count=snapshot_row.get("query_count", 0),
            )
        
        return ConversationDetailResponse(
            session_id=session_id,
            title=session["title"],
            messages=[
                ConversationMessage(
                    id=m.get("id"),
                    role=m["role"],
                    content=m["content"],
                    message_type=m.get("message_type", "chat"),
                    status=m.get("status", "completed"),
                    created_at=str(m["created_at"]) if m.get("created_at") else None,
                )
                for m in msgs
            ],
            snapshot=snapshot,
            has_more=has_more,
            created_at=str(session["created_at"]) if session.get("created_at") else None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get conversation messages %s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/api/v1/conversations/{session_id}")
async def rename_conversation(session_id: str, http_request: Request, body: dict):
    """Rename a conversation (sets title_source to 'manual' to prevent auto-override)."""
    user_id, _ = _get_user_from_request(http_request)
    title = str(body.get("title", "")).strip()[:60]
    if not title:
        raise HTTPException(status_code=400, detail="title 不能为空")
    db = get_db_service()
    # Check ownership
    session = await db.get_session_by_id(session_id, user_id=user_id if user_id else None)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.update_session_title(session_id, title, title_source="manual")
    return {"session_id": session_id, "title": title}


@app.delete("/api/v1/conversations/{session_id}")
async def delete_conversation(session_id: str, http_request: Request):
    """Delete a conversation and all its messages."""
    user_id, _ = _get_user_from_request(http_request)
    db = get_db_service()
    # Check ownership
    session = await db.get_session_by_id(session_id, user_id=user_id if user_id else None)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.delete_conversation(session_id, user_id=user_id if user_id else None)
    return {"message": "会话已删除"}


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
