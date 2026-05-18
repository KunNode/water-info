"""FastAPI application entry point backed by LangGraph."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger as loguru_logger

from app.api.risk_scan import router as risk_scan_router
from app.config import get_settings
from app.database import get_db_service
from app.graph import build_flood_response_graph, flood_response_graph
from app.langgraph_persistence import get_langgraph_persistence
from app.memory.service import build_memory_namespaces
from app.models import (
    ApprovalRequest,
    ApprovalResponse,
    CheckpointSummary,
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
    KBDocumentDetail,
    KBDocumentSummary,
    KBDocumentUploadResponse,
    KBSearchHit,
    KBSearchRequest,
    KBStatsResponse,
    MemoryItemResponse,
    MemoryItemUpdateRequest,
    PlanDetailResponse,
    PlanExecuteRequest,
    PlanExecuteResponse,
    PlanProgressResponse,
    ResumeRequest,
    ResumeResponse,
    SessionResponse,
)
from app.platform.audit_recorder import AuditRecorder, set_audit_recorder
from app.platform.human_in_the_loop import HumanInTheLoopGateway
from app.platform.skill_registry import get_skill_registry
from app.rag.service import get_knowledge_base_service
from app.services import session as session_service
from app.services.llm import get_llm
from app.services.plan_persistence import SOURCE_MANUAL, build_trigger_conditions, should_persist_plan
from app.state import set_stream_queue
from app.services.plan_review import PlanReviewError, PlanReviewService, Reviewer, StateConflictError
from app.services.platform_client import get_platform_client
from app.services.risk_scan_scheduler import get_risk_scan_scheduler
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
STREAM_KEEPALIVE_INTERVAL = 15

# Cancel events for in-flight plan executions (plan_id -> asyncio.Event)
_plan_cancel_events: dict[str, asyncio.Event] = {}


def _get_user_from_request(request: Request) -> tuple[str, str]:
    """Extract user identity from request headers."""
    user_id = request.headers.get(HEADER_USER_ID, "")
    username = request.headers.get(HEADER_USERNAME, "")
    return user_id, username


def _plan_review_http_error(exc: PlanReviewError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "errorCode": exc.error_code,
            "message": exc.message,
            **(exc.details or {}),
        },
    )


async def _get_reviewer_from_request(request: Request) -> Reviewer:
    user_id, username = _get_user_from_request(request)
    if not user_id or not username or len(user_id) > 255 or len(username) > 255:
        raise HTTPException(
            status_code=400,
            detail={"errorCode": "MISSING_IDENTITY", "message": "身份信息缺失或无效"},
        )
    if not await get_db_service().user_exists(user_id):
        raise HTTPException(
            status_code=400,
            detail={"errorCode": "UNKNOWN_REVIEWER", "message": "审核人身份无法识别"},
        )
    return Reviewer(user_id=user_id, username=username)


async def _get_plan_review_service() -> PlanReviewService:
    return PlanReviewService(await get_db_service()._get_pool())


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


def _risk_level_value(assessment: RiskAssessment | None) -> str:
    if not assessment:
        return "none"
    return assessment.risk_level.value


def _memory_item_response(row: dict) -> MemoryItemResponse:
    return MemoryItemResponse(
        id=int(row["id"]),
        namespace=str(row.get("namespace") or ""),
        item_type=str(row.get("item_type") or "fact"),
        content=str(row.get("content") or ""),
        importance=float(row.get("importance") or 0.5),
        confidence=float(row.get("confidence") or 0.5),
        metadata=row.get("metadata") or {},
        source_session_id=str(row.get("source_session_id") or "") or None,
        updated_at=str(row.get("updated_at")) if row.get("updated_at") else None,
    )


def _build_initial_state(
    session_id: str,
    query: str,
    history: list[dict],
    *,
    user_id: str = "",
    username: str = "",
) -> dict:
    return {
        "session_id": session_id,
        "user_id": user_id,
        "username": username,
        "user_query": query,
        "messages": history + [{"role": "user", "content": query}],
        "iteration": 0,
    }


def _normalize_history_messages(rows: list[dict]) -> list[dict[str, str]]:
    """Keep only completed chat turns that are safe to pass back into the graph."""
    messages: list[dict[str, str]] = []
    for row in rows:
        role = str(row.get("role") or "")
        content = str(row.get("content") or "").strip()
        status = str(row.get("status") or "completed")
        if role not in {"user", "assistant"} or not content or status in {"failed", "streaming"}:
            continue
        messages.append({"role": role, "content": content})
    return messages


async def _load_session_history(session_id: str, db, sessions) -> list[dict[str, str]]:
    """Load short-term dialogue history when LangGraph checkpointing is unavailable.

    LangGraph's Postgres checkpointer already restores thread-scoped state by
    thread_id=session_id. When it is active, adding Redis/DB history again would
    duplicate old messages because the state reducer appends messages.
    """
    if get_langgraph_persistence().enabled:
        return []

    try:
        history = _normalize_history_messages(await sessions.get_history(session_id))
        if history:
            return history
    except Exception as exc:
        logger.debug("[%s] Redis session history load skipped: %s", session_id, exc)

    try:
        rows = await db.get_conversation_messages(session_id, limit=20)
        return _normalize_history_messages(rows)
    except Exception as exc:
        logger.debug("[%s] DB session history fallback skipped: %s", session_id, exc)
        return []


async def _save_short_term_turn(sessions, session_id: str, role: str, content: str) -> None:
    """Mirror a completed chat turn into Redis short-term memory."""
    if not content:
        return
    try:
        await sessions.save_turn(session_id, role, content)
    except Exception as exc:
        logger.debug("[%s] Redis session turn save skipped: %s", session_id, exc)


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
    final_response = update.get("final_response")
    final_response_draft = update.get("final_response_draft")
    intermediate_agents = {
        "data_analyst",
        "risk_assessor",
        "plan_generator",
        "resource_dispatcher",
        "notification",
        "execution_monitor",
        "parallel_dispatch",
    }
    # Suppress agent_message when this update is a draft destined for final_response_node:
    # the same text would otherwise reach the client twice (once as the upstream agent's
    # message, once as the authoritative final_response).
    if content and not final_response and not final_response_draft and agent not in intermediate_agents:
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

    if final_response:
        events.append({
            "type": "agent_message",
            "agent": "final_response",
            "content": final_response,
            "response": final_response,
        })

    if update.get("evidence"):
        events.append({
            "type": "evidence_update",
            "agent": agent,
            "items": to_plain_data(update["evidence"]),
        })

    for trace in (update.get("execution_traces") or []):
        events.append({
            "type": "trace_update",
            "phase": trace.get("phase", ""),
            "status": trace.get("status", "completed"),
            "title": trace.get("title", ""),
            "detail": trace.get("detail", ""),
            "tool_name": trace.get("tool_name"),
            "metadata": trace.get("metadata", {}),
        })

    events.append({"type": "agent_update", "agent": agent, "status": "done"})
    return events


def _normalize_reasoning_status(status_raw: str) -> str:
    """Map heterogeneous trace status values to the frontend's 4-state enum."""
    normalized = (status_raw or "").lower()
    if normalized in {"completed", "success", "done"}:
        return "success"
    if normalized in {"failed", "error"}:
        return "error"
    if normalized in {"running", "in_progress", "started"}:
        return "running"
    return "success"


def _reasoning_steps_from_final_state(final_state: dict) -> list[dict]:
    """Build ``conversation_messages.metadata.reasoning_steps`` from graph state.

    Merges ``execution_traces`` (and any future thought steps exposed on the
    state) into the JSONB schema documented in design §1: each entry carries
    ``id / kind / title / content / status / duration_ms`` plus an optional
    ``tool`` sub-object for ``kind == "tool"``.

    This is a *pure* function: deterministic, no clock access, no I/O. Missing
    fields fall back to safe defaults; non-dict inputs yield an empty list.
    """
    if not isinstance(final_state, dict):
        return []
    traces = final_state.get("execution_traces") or []
    steps: list[dict] = []
    for idx, trace in enumerate(traces):
        if not isinstance(trace, dict):
            continue
        tool_name = trace.get("tool_name")
        kind = "tool" if tool_name else "thought"
        metadata = trace.get("metadata") if isinstance(trace.get("metadata"), dict) else {}
        step: dict = {
            "id": f"{kind}-{idx}",
            "kind": kind,
            "title": str(trace.get("title") or ""),
            "content": str(trace.get("detail") or ""),
            "status": _normalize_reasoning_status(str(trace.get("status") or "completed")),
        }
        duration_ms = metadata.get("duration_ms")
        if isinstance(duration_ms, (int, float)) and not isinstance(duration_ms, bool):
            step["duration_ms"] = int(duration_ms)
        if kind == "tool":
            tool_obj: dict = {
                "name": str(tool_name),
                "display_name": str(trace.get("title") or tool_name),
            }
            input_summary = metadata.get("input_summary")
            result_summary = metadata.get("output_summary")
            if input_summary:
                tool_obj["input_summary"] = str(input_summary)
            if result_summary:
                tool_obj["result_summary"] = str(result_summary)
            step["tool"] = tool_obj
        steps.append(step)
    return steps


def _tool_calls_from_traces(traces: list[dict] | None) -> list[dict]:
    """Flatten tool-class traces into ``metadata.tool_calls[]``.

    Each emitted entry matches the design §1 schema:
    ``{tool_call_id, tool_name, arguments, result, error, duration_ms}``.
    A trace is considered tool-class when it carries ``tool_name`` or has
    ``phase == "tool_call"``. Other traces are skipped so the audit panel only
    sees real tool invocations.

    Pure function: deterministic mapping, never raises.
    """
    if not traces:
        return []
    calls: list[dict] = []
    for idx, trace in enumerate(traces):
        if not isinstance(trace, dict):
            continue
        tool_name = trace.get("tool_name")
        phase = str(trace.get("phase") or "")
        if not tool_name and phase != "tool_call":
            continue
        metadata = trace.get("metadata") if isinstance(trace.get("metadata"), dict) else {}
        input_summary = metadata.get("input_summary")
        output_summary = metadata.get("output_summary")
        duration_ms = metadata.get("duration_ms")
        status_raw = str(trace.get("status") or "").lower()
        detail = str(trace.get("detail") or "")
        error_msg = detail if status_raw in {"failed", "error"} and detail else None
        call: dict = {
            "tool_call_id": f"tool-{idx}-{tool_name or phase}",
            "tool_name": str(tool_name or ""),
            "arguments": {"input_summary": str(input_summary)} if input_summary else {},
            "result": {"output_summary": str(output_summary)} if output_summary else {},
            "error": error_msg,
        }
        if isinstance(duration_ms, (int, float)) and not isinstance(duration_ms, bool):
            call["duration_ms"] = int(duration_ms)
        calls.append(call)
    return calls


def _serialize_kb_document(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "title": str(row["title"]),
        "source_type": str(row.get("source_type") or ""),
        "source_uri": str(row.get("source_uri") or ""),
        "mime": str(row.get("mime") or ""),
        "lang": str(row.get("lang") or "zh-CN"),
        "version": int(row.get("version") or 1),
        "status": str(row.get("status") or "pending"),
        "chunk_count": int(row.get("chunk_count") or 0),
        "file_size": int(row.get("file_size") or 0),
        "embedding_model": str(row.get("embedding_model") or "") or None,
        "created_by": str(row.get("created_by") or "") or None,
        "latest_job_status": str(row.get("latest_job_status") or "") or None,
        "latest_error": str(row.get("latest_error") or "") or None,
        "metadata": row.get("metadata") or {},
        "created_at": str(row["created_at"]) if row.get("created_at") else None,
        "updated_at": str(row["updated_at"]) if row.get("updated_at") else None,
        "last_indexed_at": str(row["last_indexed_at"]) if row.get("last_indexed_at") else None,
    }


async def _do_execute_plan(plan_id: str, actions: list[dict]) -> None:
    db = get_db_service()
    platform = get_platform_client()
    cancel_event = _plan_cancel_events.get(plan_id)
    failed = 0
    cancelled = False
    for action in actions:
        action_id = action.get("action_id", "")
        # Check cancel flag
        if cancel_event and cancel_event.is_set():
            cancelled = True
            break
        # Skip actions already manually updated to a terminal state
        current = await db.get_action_status(plan_id, action_id)
        if current in ("completed", "failed"):
            if current == "failed":
                failed += 1
            continue
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
    # Clean up cancel event
    _plan_cancel_events.pop(plan_id, None)
    if cancelled:
        await db.update_plan_status(plan_id, "cancelled")
    elif failed > 0:
        await db.update_plan_status(plan_id, "failed")
    else:
        await db.update_plan_status(plan_id, "completed")


# ── lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    global flood_response_graph
    logger.info("启动水务AI多 Agent 应急服务")

    # OTel tracer init (Task 9.7)
    if settings.otel_enabled:
        try:
            from app.observability.otel import init_tracer_provider
            init_tracer_provider()
        except Exception as exc:
            logger.warning("OTel init failed (non-fatal): %s", exc)

    db = get_db_service()
    sessions = session_service.get_session_service()
    persistence = get_langgraph_persistence()
    try:
        await db._get_pool()
        await db.ensure_plan_tables()
        await db.ensure_conversation_tables()
        await db.ensure_kb_tables()
        logger.info("数据库连接池就绪")
        if await persistence.start():
            flood_response_graph = build_flood_response_graph(
                checkpointer=persistence.checkpointer,
                store=persistence.store,
            )
    except Exception as exc:
        logger.warning("数据库预热失败（服务仍可启动）: %s", exc)
    if settings.skill_registry_enabled:
        try:
            registry = get_skill_registry()
            registry.load_all()
            app.state.skill_registry = registry
            logger.info("SkillRegistry loaded %s skills", len(registry.skills))
        except Exception as exc:
            logger.warning("SkillRegistry initialization failed; continuing without skills: %s", exc)
    app.state.audit_recorder = AuditRecorder(
        get_platform_client(),
        enabled=settings.audit_tables_enabled,
    )
    set_audit_recorder(app.state.audit_recorder)
    app.state.hil_gateway = HumanInTheLoopGateway()
    await get_risk_scan_scheduler().start()
    yield
    await get_risk_scan_scheduler().stop()
    await persistence.aclose()
    await db.close()
    await sessions.close()
    await get_platform_client().close()
    try:
        await get_llm().aclose()
    except RuntimeError:
        logger.debug("LLM client already closed with event loop shutdown")
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

app.include_router(risk_scan_router)


# ── OTel trace-id middleware (Task 9.6) ───────────────────────────────────

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Inject ``X-Trace-Id`` header on flood query endpoints when OTel is active."""

    _FLOOD_PATHS = ("/api/v1/flood/query", "/api/v1/flood/query/stream")

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path in self._FLOOD_PATHS:
            from app.observability.otel import current_trace_id_hex

            trace_id = current_trace_id_hex()
            if trace_id:
                response.headers["X-Trace-Id"] = trace_id
        return response


if settings.otel_enabled:
    app.add_middleware(TraceIdMiddleware)


# ── endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse()


@app.post("/api/v1/flood/query", response_model=FloodQueryResponse)
async def flood_query(request: FloodQueryRequest, http_request: Request) -> FloodQueryResponse:
    """Execute flood emergency query (non-streaming)."""
    user_id, username = _get_user_from_request(http_request)
    session_id = request.session_id or str(uuid.uuid4())
    logger.info("[%s] flood query from user=%s: %s", session_id, user_id or "anonymous", request.query[:80])

    db = get_db_service()
    sessions = session_service.get_session_service()

    # Auto-create session using first 30 chars of query as title (first message creates session)
    title = request.query[:30] + ("…" if len(request.query) > 30 else "")
    await db.ensure_or_create_session(
        session_id, title, user_id=user_id, username=username, title_source="auto_first_query"
    )

    history = await _load_session_history(session_id, db, sessions)
    # Save user message with new schema
    await db.save_conversation_message(session_id, "user", request.query, message_type="chat", status="completed")
    await _save_short_term_turn(sessions, session_id, "user", request.query)

    try:
        final_state = await flood_response_graph.ainvoke(
            _build_initial_state(session_id, request.query, history, user_id=user_id, username=username),
            {"configurable": {"thread_id": session_id}},
        )
    except Exception as exc:
        logger.exception("[%s] graph failed: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=f"处理失败: {exc}") from exc
    final_state.setdefault("session_id", session_id)
    final_state.setdefault("user_query", request.query)

    # HITL interrupt detection (Task 20.4 — non-streaming)
    if final_state.get("next_agent") == "__interrupt__":
        approval_info = final_state.get("human_review") or {}
        approval_id = approval_info.get("approval_id") or str(uuid.uuid4())
        try:
            from app.platform.approvals import PendingApprovalRow, get_approvals_dao

            dao = await get_approvals_dao()
            await dao.insert_pending(PendingApprovalRow(
                approval_id=approval_id,
                session_id=session_id,
                approval_type="critical_action_review",
                payload_json={"original_next_agent": approval_info.get("original_next_agent", ""), "query": request.query},
            ))
        except Exception as exc:
            logger.warning("[%s] failed to persist pending approval: %s", session_id, exc)
        raise HTTPException(
            status_code=202,
            detail={
                "status": "approval_required",
                "approval_id": approval_id,
                "session_id": session_id,
                "message": "操作需要人工审核，请审批后继续",
            },
        )

    # Req 4.4: if memory_loader short-circuited the graph because a critical
    # store (summary / snapshot / conversation_messages) failed to read, the
    # graph will return with ``error="memory_load_failed: <source>"`` instead
    # of a real ``final_response``. The SSE path handles this inside
    # ``event_stream``; the non-stream handler must mirror that contract so it
    # does not fabricate a success reply on top of the user's question. We:
    #   * do NOT persist an assistant message (the user message has already
    #     been written above and keeps the audit trail intact);
    #   * do NOT fire the background ``_persist_result`` task (no plan exists);
    #   * raise 503 to communicate that the dependency is temporarily
    #     unavailable rather than a generic 500.
    error_str = str(final_state.get("error") or "")
    if error_str.startswith("memory_load_failed:"):
        source = error_str.split(":", 1)[1].strip() or "unknown"
        loguru_logger.error(
            "[{session_id}] flood_query aborted: memory load failed (source={source})",
            session_id=session_id,
            source=source,
        )
        raise HTTPException(status_code=503, detail="会话历史加载失败，请稍后重试")

    # Save assistant response
    response_content = final_state.get("final_response") or "处理完成"
    await db.save_conversation_message(session_id, "assistant", response_content, message_type="chat", status="completed")
    await _save_short_term_turn(sessions, session_id, "assistant", response_content)

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

        history = await _load_session_history(session_id, db, sessions)

        # Save user message
        await db.save_conversation_message(session_id, "user", request.query, message_type="chat", status="completed")
        await _save_short_term_turn(sessions, session_id, "user", request.query)

        # Create assistant placeholder message with streaming status
        assistant_msg_id = await db.save_conversation_message(
            session_id, "assistant", "", message_type="chat", status="streaming"
        )

        final_state = None
        accumulated_response = ""

        # Create streaming queue for token-level streaming
        stream_queue: asyncio.Queue[str | None] = asyncio.Queue()
        answer_started = False

        try:
            yield _event_line({"type": "session_init", "sessionId": session_id})

            # Set stream queue in context (avoids pickle issues)
            set_stream_queue(stream_queue)

            graph_iter = flood_response_graph.astream(
                _build_initial_state(session_id, request.query, history, user_id=user_id, username=username),
                {"configurable": {"thread_id": session_id}},
                stream_mode="updates",
            ).__aiter__()

            # Background task to drain stream queue
            queue_exhausted = asyncio.Event()
            pending_queue_lines: list[str] = []

            async def drain_queue():
                """Consume tokens from queue, buffer SSE lines."""
                nonlocal answer_started, accumulated_response
                while True:
                    token = await stream_queue.get()
                    if token is None:  # Sentinel: streaming complete
                        break
                    if not answer_started:
                        answer_started = True
                        pending_queue_lines.append(_event_line({"type": "answer_start"}))
                    accumulated_response += token
                    pending_queue_lines.append(_event_line({"type": "answer_delta", "delta": token}))
                queue_exhausted.set()

            drain_task = asyncio.create_task(drain_queue())

            # Run graph updates and queue draining concurrently
            pending_update = asyncio.create_task(graph_iter.__anext__())

            while True:
                try:
                    update = await asyncio.wait_for(
                        asyncio.shield(pending_update),
                        timeout=STREAM_KEEPALIVE_INTERVAL,
                    )
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    yield ":keepalive\n\n"
                    continue
                node_name, node_update = next(iter(update.items()))
                final_state = {**(final_state or {}), **node_update}
                # Req 4.4: if memory_loader short-circuited the graph because a
                # critical store (summary / snapshot / conversation_messages)
                # failed to read, surface a structured SSE ``error`` event and
                # terminate the stream. The error string format is produced by
                # ``memory_loader_node`` as ``"memory_load_failed: <source>"``.
                error_str = str(final_state.get("error") or "")
                if error_str.startswith("memory_load_failed:"):
                    source = error_str.split(":", 1)[1].strip() or "unknown"
                    loguru_logger.error(
                        "[{session_id}] SSE error: memory load failed (source={source})",
                        session_id=session_id,
                        source=source,
                    )
                    try:
                        await db.update_message_content(
                            assistant_msg_id,
                            "会话历史加载失败，请稍后重试",
                            status="failed",
                        )
                    except Exception:
                        pass
                    yield _event_line({
                        "type": "error",
                        "message": "会话历史加载失败，请稍后重试",
                        "code": "memory_load_failed",
                        "recoverable": False,
                    })
                    return

                # Yield any buffered streaming tokens first
                while pending_queue_lines:
                    yield pending_queue_lines.pop(0)

                for event in _build_stream_events(node_name, node_update):
                    # Skip agent_message for final_response if we're streaming tokens
                    if (
                        event.get("type") == "agent_message"
                        and event.get("agent") == "final_response"
                        and answer_started
                    ):
                        accumulated_response = event.get("response", "")
                        continue
                    yield _event_line(event)
                pending_update = asyncio.create_task(graph_iter.__anext__())

            # Signal queue exhaustion and wait for drain to complete
            await stream_queue.put(None)  # Send sentinel
            await drain_task

            # Yield any remaining buffered lines
            while pending_queue_lines:
                yield pending_queue_lines.pop(0)

            # Send answer_end if we streamed tokens
            if answer_started:
                yield _event_line({"type": "answer_end"})

            # HITL interrupt detection (Task 20.4)
            if final_state and final_state.get("next_agent") == "__interrupt__":
                approval_info = final_state.get("human_review") or {}
                approval_id = approval_info.get("approval_id") or str(uuid.uuid4())
                # Persist pending approval to DB
                try:
                    from app.platform.approvals import get_approvals_dao

                    dao = await get_approvals_dao()
                    from app.platform.approvals import PendingApprovalRow

                    await dao.insert_pending(PendingApprovalRow(
                        approval_id=approval_id,
                        session_id=session_id,
                        approval_type="critical_action_review",
                        payload_json={
                            "original_next_agent": approval_info.get("original_next_agent", ""),
                            "query": request.query,
                        },
                    ))
                except Exception as exc:
                    logger.warning("[%s] failed to persist pending approval: %s", session_id, exc)
                yield _event_line({
                    "type": "approval_required",
                    "approval_id": approval_id,
                    "session_id": session_id,
                    "approval_type": "critical_action_review",
                    "message": "操作需要人工审核，请审批后继续",
                })
                yield _event_line({"type": "agent_update", "agent": "__done__", "status": "interrupted"})
                return

            if final_state:
                final_state.setdefault("session_id", session_id)
                final_state.setdefault("user_query", request.query)
                final_response = final_state.get("final_response") or accumulated_response or "处理完成"
                # Build metadata following the JSONB contract defined in design §1.
                # reasoning_steps + tool_calls are derived from execution_traces; the
                # execution_traces array is also persisted as-is for the audit panel.
                # The `agent` field falls back to "final_response" when the graph state
                # did not mark a current agent (mirrors design §8).
                exec_traces = final_state.get("execution_traces") or []
                trace_metadata: dict = {
                    "version": 1,
                    "agent": final_state.get("current_agent") or "final_response",
                    "reasoning_steps": _reasoning_steps_from_final_state(final_state),
                    "execution_traces": exec_traces,
                    "tool_calls": _tool_calls_from_traces(exec_traces),
                }
                # Update assistant message to completed with full metadata contract.
                await db.update_message_content(
                    assistant_msg_id, final_response, status="completed",
                    metadata=trace_metadata,
                )
                await _save_short_term_turn(sessions, session_id, "assistant", final_response)
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


# ── knowledge base endpoints ──────────────────────────────────────────────────


@app.post("/api/v1/kb/documents", response_model=KBDocumentUploadResponse)
async def upload_kb_document(
    background_tasks: BackgroundTasks,
    http_request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    source_uri: str | None = Form(default=None),
):
    user_id, username = _get_user_from_request(http_request)

    filename = file.filename or "upload"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")

    actor = username or user_id or "system"

    service = get_knowledge_base_service()
    document_id, job_id = await service.create_upload_job(
        filename=filename,
        content=content,
        title=title,
        source_uri=source_uri or filename,
        mime=file.content_type,
        created_by=actor,
    )
    background_tasks.add_task(
        service.ingest_document_bytes,
        document_id=document_id,
        job_id=job_id,
        filename=filename,
        content=content,
        title=title,
        source_uri=source_uri or filename,
        mime=file.content_type,
        created_by=actor,
    )
    return KBDocumentUploadResponse(document_id=document_id, job_id=job_id, status="pending")


@app.get("/api/v1/kb/documents", response_model=list[KBDocumentSummary])
async def list_kb_documents(
    status: str | None = None,
    source_type: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    rows = await get_db_service().list_kb_documents(
        status=status,
        source_type=source_type,
        q=q,
        limit=limit,
        offset=offset,
    )
    return [KBDocumentSummary.model_validate(_serialize_kb_document(row)) for row in rows]


@app.get("/api/v1/kb/documents/{document_id}", response_model=KBDocumentDetail)
async def get_kb_document(document_id: str):
    row = await get_db_service().get_kb_document(document_id)
    if not row:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    return KBDocumentDetail.model_validate(_serialize_kb_document(row))


@app.delete("/api/v1/kb/documents/{document_id}")
async def delete_kb_document(document_id: str, http_request: Request):
    deleted = await get_db_service().soft_delete_kb_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    return {"message": "文档已删除"}


@app.post("/api/v1/kb/documents/{document_id}/reindex", response_model=KBDocumentUploadResponse)
async def reindex_kb_document(document_id: str, background_tasks: BackgroundTasks, http_request: Request):
    row = await get_db_service().get_kb_document(document_id)
    if not row:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    job_id = await get_db_service().create_kb_ingest_job(document_id)
    background_tasks.add_task(get_knowledge_base_service().reindex_document, document_id, job_id=job_id)
    return KBDocumentUploadResponse(document_id=document_id, job_id=job_id, status="pending")


@app.post("/api/v1/kb/search", response_model=list[KBSearchHit])
async def search_kb_documents(request: KBSearchRequest):
    rows = await get_knowledge_base_service().search(
        request.query,
        top_k=request.top_k,
        source_types=request.source_types,
    )
    return [KBSearchHit.model_validate(to_plain_data(row)) for row in rows]


@app.get("/api/v1/kb/stats", response_model=KBStatsResponse)
async def get_kb_stats():
    return KBStatsResponse.model_validate(await get_db_service().get_kb_stats())


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
            version=plan.get("version") or 0,
            actions=await db.get_plan_actions(plan_id),
            resources=await db.get_plan_resources(plan_id),
            notifications=await db.get_plan_notifications(plan_id),
            created_at=str(plan["created_at"]) if plan.get("created_at") else None,
            updated_at=str(plan["updated_at"]) if plan.get("updated_at") else None,
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
        status = plan["status"]
        if status not in ("approved", "failed", "cancelled"):
            raise HTTPException(status_code=409, detail=f"当前状态 '{status}' 不允许执行，需为 approved/failed/cancelled")
        # Reset actions if re-executing from a terminal state
        if status in ("failed", "cancelled"):
            await db.reset_plan_actions(plan_id)
        actions = await db.get_plan_actions(plan_id)
        if request and request.action_ids:
            actions = [a for a in actions if a.get("action_id") in request.action_ids]
        # Register cancel event (cleared on success or explicit cancel)
        _plan_cancel_events[plan_id] = asyncio.Event()
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


@app.get("/api/v1/plans/{plan_id}/progress", response_model=PlanProgressResponse)
async def get_plan_progress(plan_id: str):
    try:
        db = get_db_service()
        plan = await db.get_emergency_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="预案不存在")
        actions = await db.get_plan_actions(plan_id)
        completed = sum(1 for a in actions if a.get("status") == "completed")
        failed = sum(1 for a in actions if a.get("status") == "failed")
        return PlanProgressResponse(
            plan_id=plan_id,
            plan_status=plan["status"],
            actions=actions,
            total=len(actions),
            completed=completed,
            failed=failed,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get plan progress %s: %s", plan_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/api/v1/plans/{plan_id}/actions/{action_id}")
async def update_action_status_during_execution(plan_id: str, action_id: str, body: dict):
    new_status = body.get("status")
    if new_status not in ("pending", "in_progress", "completed", "failed"):
        raise HTTPException(status_code=400, detail="status 必须为 pending/in_progress/completed/failed")
    try:
        db = get_db_service()
        plan = await db.get_emergency_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="预案不存在")
        if plan["status"] != "executing":
            raise HTTPException(status_code=409, detail="仅执行中的预案可修改行动状态")
        await db.update_action_status(plan_id, action_id, new_status)
        return {"plan_id": plan_id, "action_id": action_id, "status": new_status}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("update action status %s/%s: %s", plan_id, action_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/plans/{plan_id}/cancel")
async def cancel_plan(plan_id: str):
    try:
        db = get_db_service()
        plan = await db.get_emergency_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="预案不存在")
        if plan["status"] != "executing":
            raise HTTPException(status_code=409, detail="仅执行中的预案可取消")
        cancel_event = _plan_cancel_events.get(plan_id)
        if cancel_event:
            cancel_event.set()
        else:
            # Background task not tracked; set status directly
            await db.update_plan_status(plan_id, "cancelled")
        return {"plan_id": plan_id, "status": "cancelling"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("cancel plan %s: %s", plan_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/api/v1/plans/{plan_id}")
async def update_plan_content(plan_id: str, body: dict, http_request: Request):
    reviewer = await _get_reviewer_from_request(http_request)
    version = body.get("version")
    if version is None:
        raise HTTPException(status_code=400, detail={"errorCode": "BAD_VERSION", "message": "version 必填"})

    db = get_db_service()
    plan = await db.get_emergency_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail={"errorCode": "PLAN_NOT_FOUND", "message": "预案不存在"})

    patch = {key: value for key, value in body.items() if key != "version"}
    service = await _get_plan_review_service()
    try:
        if plan["status"] == "draft":
            return await service.edit_draft(plan_id, int(version), patch, reviewer)
        if plan["status"] == "approved":
            return await service.edit_approved(plan_id, int(version), patch, reviewer)
        raise StateConflictError(plan["status"], ["draft", "approved"])
    except PlanReviewError as exc:
        raise _plan_review_http_error(exc) from exc


@app.post("/api/v1/plans/{plan_id}/approve")
async def approve_plan(plan_id: str, body: dict, http_request: Request):
    reviewer = await _get_reviewer_from_request(http_request)
    version = body.get("version")
    if version is None:
        raise HTTPException(status_code=400, detail={"errorCode": "BAD_VERSION", "message": "version 必填"})

    try:
        service = await _get_plan_review_service()
        return await service.approve(plan_id, int(version), str(body.get("opinion") or ""), reviewer)
    except PlanReviewError as exc:
        raise _plan_review_http_error(exc) from exc


@app.get("/api/v1/plans/{plan_id}/audits")
async def list_plan_audits(plan_id: str, http_request: Request):
    await _get_reviewer_from_request(http_request)
    if not await get_db_service().get_emergency_plan(plan_id):
        raise HTTPException(status_code=404, detail={"errorCode": "PLAN_NOT_FOUND", "message": "预案不存在"})
    return await get_db_service().list_plan_audits(plan_id)


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
            plan_info = snapshot_row.get("plan_info")
            agent_status = snapshot_row.get("agent_status_summary")
            snapshot = ConversationSnapshot(
                risk_level=snapshot_row.get("risk_level", "none"),
                plan_info=json.loads(plan_info) if isinstance(plan_info, str) else plan_info,
                agent_status_summary=json.loads(agent_status) if isinstance(agent_status, str) else agent_status,
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


@app.get("/api/v1/memory", response_model=list[MemoryItemResponse])
async def list_memory(http_request: Request, session_id: str | None = None, limit: int = 50, offset: int = 0):
    """List active long-term memory items visible to the current user/session."""
    user_id, _ = _get_user_from_request(http_request)
    namespaces = build_memory_namespaces(user_id, session_id or "")
    rows = await get_db_service().list_memory_items(namespaces=namespaces, limit=limit, offset=offset)
    return [_memory_item_response(row) for row in rows]


@app.get("/api/v1/memory/user", response_model=list[MemoryItemResponse])
async def list_user_memory(http_request: Request, limit: int = 50, offset: int = 0):
    """List active long-term memory items owned by the current user namespace."""
    user_id, _ = _get_user_from_request(http_request)
    if not user_id:
        raise HTTPException(status_code=400, detail="缺少用户身份")
    namespace = f"user:{user_id}:flood_assistant"
    rows = await get_db_service().list_memory_items(namespaces=[namespace], limit=limit, offset=offset)
    return [_memory_item_response(row) for row in rows]


@app.patch("/api/v1/memory/{memory_id}", response_model=MemoryItemResponse)
async def update_memory(memory_id: int, request: MemoryItemUpdateRequest, http_request: Request, session_id: str | None = None):
    """Update or disable a memory item in the current user's visible namespace."""
    if request.content is not None and not request.content.strip():
        raise HTTPException(status_code=400, detail="记忆内容不能为空")
    if request.item_type is not None and not request.item_type.strip():
        raise HTTPException(status_code=400, detail="记忆类型不能为空")

    user_id, _ = _get_user_from_request(http_request)
    namespaces = build_memory_namespaces(user_id, session_id or "")
    row = await get_db_service().update_memory_item(
        memory_id,
        namespaces=namespaces,
        item_type=request.item_type,
        content=request.content,
        importance=request.importance,
        confidence=request.confidence,
        metadata=request.metadata,
        status=request.status,
    )
    if not row:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return _memory_item_response(row)


@app.delete("/api/v1/memory/{memory_id}")
async def delete_memory(memory_id: int, http_request: Request, session_id: str | None = None):
    """Soft-delete a memory item in the current user's visible namespace."""
    user_id, _ = _get_user_from_request(http_request)
    namespaces = build_memory_namespaces(user_id, session_id or "")
    deleted = await get_db_service().delete_memory_item(memory_id, namespaces=namespaces)
    if not deleted:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"deleted": True}


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
            plan_info = snapshot_row.get("plan_info")
            agent_status = snapshot_row.get("agent_status_summary")
            snapshot = ConversationSnapshot(
                risk_level=snapshot_row.get("risk_level", "none"),
                plan_info=json.loads(plan_info) if isinstance(plan_info, str) else plan_info,
                agent_status_summary=json.loads(agent_status) if isinstance(agent_status, str) else agent_status,
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
                    metadata=json.loads(m["metadata"]) if isinstance(m.get("metadata"), str) else m.get("metadata"),
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


# ── checkpoint / resume endpoints (supervisor-autogen-enhancements F4) ────


@app.get("/api/v1/flood/sessions/{session_id}/checkpoints", response_model=list[CheckpointSummary])
async def list_checkpoints(session_id: str):
    """List up to 50 most recent checkpoints for a session.

    Returns 503 when LANGGRAPH_POSTGRES_ENABLED is false.
    """
    settings = get_settings()
    if not settings.langgraph_postgres_enabled:
        raise HTTPException(
            status_code=503,
            detail={"error_code": "persistence_disabled", "message": "Checkpoint persistence is not enabled"},
        )
    persistence = get_langgraph_persistence()
    if not persistence.enabled or persistence.checkpointer is None:
        raise HTTPException(
            status_code=503,
            detail={"error_code": "persistence_disabled", "message": "Checkpoint persistence is not available"},
        )

    config = {"configurable": {"thread_id": session_id}}
    summaries: list[CheckpointSummary] = []
    async for checkpoint_tuple in persistence.checkpointer.alist(config, limit=50):
        state = checkpoint_tuple.checkpoint.get("channel_values", {})
        cp_config = checkpoint_tuple.config
        checkpoint_id = cp_config.get("configurable", {}).get("checkpoint_id", "")
        created_at = checkpoint_tuple.metadata.get("created_at", "") if checkpoint_tuple.metadata else ""
        summaries.append(CheckpointSummary(
            checkpoint_id=str(checkpoint_id),
            last_completed_agent=str(state.get("current_agent", "")),
            created_at=str(created_at),
            current_state_summary={
                "intent": state.get("intent", ""),
                "safety_level": state.get("safety_level", ""),
                "has_data_summary": bool(state.get("data_summary")),
                "has_risk_assessment": state.get("risk_assessment") is not None,
                "has_emergency_plan": state.get("emergency_plan") is not None,
                "has_resource_plan": bool(state.get("resource_plan")),
                "has_notifications": bool(state.get("notifications")),
            },
        ))
    return summaries


@app.post("/api/v1/flood/sessions/{session_id}/resume", response_model=ResumeResponse)
async def resume_session(session_id: str, body: ResumeRequest):
    """Resume a graph execution from a checkpoint.

    Returns 503 when persistence disabled, 404 when checkpoint not found,
    409 when duplicate resume is in progress, 200 on success.
    """
    settings = get_settings()
    if not settings.langgraph_postgres_enabled:
        raise HTTPException(
            status_code=503,
            detail={"error_code": "persistence_disabled", "message": "Checkpoint persistence is not enabled"},
        )
    persistence = get_langgraph_persistence()
    if not persistence.enabled or persistence.checkpointer is None:
        raise HTTPException(
            status_code=503,
            detail={"error_code": "persistence_disabled", "message": "Checkpoint persistence is not available"},
        )

    # Find the target checkpoint
    config = {"configurable": {"thread_id": session_id}}
    target_checkpoint = None

    if body.checkpoint_id:
        # Look for specific checkpoint
        async for checkpoint_tuple in persistence.checkpointer.alist(config, limit=50):
            cp_id = checkpoint_tuple.config.get("configurable", {}).get("checkpoint_id", "")
            if str(cp_id) == body.checkpoint_id:
                target_checkpoint = checkpoint_tuple
                break
        if target_checkpoint is None:
            raise HTTPException(
                status_code=404,
                detail={"error_code": "checkpoint_not_found", "message": f"Checkpoint {body.checkpoint_id} not found"},
            )
    else:
        # Use most recent checkpoint
        async for checkpoint_tuple in persistence.checkpointer.alist(config, limit=1):
            target_checkpoint = checkpoint_tuple
            break
        if target_checkpoint is None:
            raise HTTPException(
                status_code=404,
                detail={"error_code": "no_checkpoints_for_session", "message": f"No checkpoints found for session {session_id}"},
            )

    # Check idempotency
    import hashlib

    state_json = json.dumps(target_checkpoint.checkpoint.get("channel_values", {}), sort_keys=True, default=str)
    state_sha1 = hashlib.sha1(state_json.encode()).hexdigest()
    checkpoint_id = str(target_checkpoint.config.get("configurable", {}).get("checkpoint_id", ""))

    from app.platform.resume_idempotency import get_resume_idempotency_cache

    cache = get_resume_idempotency_cache()
    if not await cache.try_acquire(checkpoint_id, state_sha1):
        raise HTTPException(
            status_code=409,
            detail={"error_code": "resume_already_in_progress", "message": "A resume with this checkpoint is already in progress"},
        )

    # Build the resume state
    run_id = str(uuid.uuid4())
    state = dict(target_checkpoint.checkpoint.get("channel_values", {}))
    state["agent_run_id"] = run_id
    state["session_id"] = session_id

    # Apply override_next_agent if provided
    if body.override_next_agent:
        state["next_agent"] = body.override_next_agent

    # Add resume trace
    last_agent = state.get("current_agent", "unknown")
    state.setdefault("execution_traces", []).append({
        "phase": "data_query",
        "status": "completed",
        "title": f"resumed from {last_agent}",
        "detail": f"checkpoint_id={checkpoint_id}",
        "tool_name": None,
        "metadata": {},
    })

    try:
        # Resume the graph from the checkpoint
        resume_config = {
            "configurable": {
                "thread_id": session_id,
                "checkpoint_id": checkpoint_id,
            }
        }
        await flood_response_graph.ainvoke(state, resume_config)
    finally:
        await cache.release(checkpoint_id, state_sha1)

    return ResumeResponse(
        status="resumed",
        run_id=run_id,
        checkpoint_id=checkpoint_id,
    )


# ── HITL approval endpoint (supervisor-autogen-enhancements F5) ────────────


@app.post("/api/v1/flood/approvals/{approval_id}", response_model=ApprovalResponse)
async def resolve_approval(approval_id: str, body: ApprovalRequest):
    """Resolve a pending HITL approval.

    Approve: resume graph from the interrupted state.
    Reject: resume to __end__ (skip downstream).
    Modify: resume with override_next_agent.
    """
    if not settings.hitl_enabled:
        raise HTTPException(status_code=503, detail="HITL is not enabled")

    from app.platform.approvals import get_approvals_dao

    dao = await get_approvals_dao()
    row = await dao.get(approval_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")

    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"Approval already {row.status}")

    # CAS resolve
    resolution = body.decision
    if body.comment:
        resolution = f"{body.decision}: {body.comment}"

    updated = await dao.cas_resolve(
        approval_id,
        new_status=body.decision + "d" if body.decision == "approve" else body.decision + "ed",
        resolution=resolution,
        resolved_by="",
    )
    if not updated:
        raise HTTPException(status_code=409, detail="Approval was already resolved (CAS)")

    # Resume the graph
    session_id = row.session_id
    resume_state: dict = {
        "session_id": session_id,
        "approval_id": approval_id,
    }

    if body.decision == "reject":
        resume_state["next_agent"] = "__end__"
        resume_state["human_review"] = {"approval_id": approval_id, "status": "rejected"}
    elif body.decision == "modify" and body.override_next_agent:
        resume_state["next_agent"] = body.override_next_agent
        resume_state["human_review"] = {"approval_id": approval_id, "status": "modified"}
    else:
        # approve — resume with original next_agent from payload
        original = (row.payload_json or {}).get("original_next_agent", "__end__")
        resume_state["next_agent"] = original
        resume_state["human_review"] = {"approval_id": approval_id, "status": "approved"}

    # Persist decision log
    try:
        from app.platform.audit_recorder import get_audit_recorder

        recorder = get_audit_recorder()
        if recorder is not None:
            from app.platform.audit_models import DecisionLogRecord

            await recorder.record_decision(DecisionLogRecord(
                session_id=session_id,
                decision_type="human_review",
                decision_json={
                    "approval_id": approval_id,
                    "decision": body.decision,
                    "comment": body.comment,
                    "override_next_agent": body.override_next_agent,
                },
                evidence_ids=[],
                human_approved=body.decision == "approve",
            ))
    except Exception as exc:
        logger.warning("Failed to record approval decision log: %s", exc)

    # Resume graph execution in background
    try:
        config = {"configurable": {"thread_id": session_id}}
        asyncio.create_task(flood_response_graph.ainvoke(resume_state, config))
    except Exception as exc:
        logger.warning("Failed to resume graph after approval: %s", exc)

    return ApprovalResponse(
        status=body.decision + "d" if body.decision == "approve" else body.decision + "ed",
        approval_id=approval_id,
        resolution=resolution,
    )
