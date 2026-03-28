"""FastAPI 应用入口

提供 REST API 供前端和 Spring Boot 后端调用。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, Field

from app.config import configure_logging, get_settings
from app.graph import flood_response_graph
from app.services.database import get_db_service
from app.services.platform_client import get_platform_client
from app.state import FloodResponseState

# 初始化日志配置（在应用启动前）
configure_logging()


# ─────────────────────────────────────────────
# 请求 / 响应模型
# ─────────────────────────────────────────────


class FloodQueryRequest(BaseModel):
    """防洪应急查询请求"""

    query: str = Field(..., description="用户请求，如：'分析当前水情并生成应急预案'")
    session_id: str = Field(default="", description="会话ID（留空自动生成）")


class FloodQueryResponse(BaseModel):
    """防洪应急查询响应"""

    session_id: str
    response: str
    risk_level: str | None = None
    risk_score: float | None = None
    plan_id: str | None = None
    plan_name: str | None = None
    actions_count: int = 0
    resources_count: int = 0
    notifications_count: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "water-info-ai"
    version: str = "0.1.0"


# ─────────────────────────────────────────────
# 生命周期
# ─────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("水务AI多智能体服务启动")
    # 预热数据库连接池 + 确保持久化表
    try:
        db = get_db_service()
        await db._get_pool()
        await db.ensure_plan_tables()
        logger.info("数据库连接池预热完成，持久化表已就绪")
    except Exception as e:
        logger.warning(f"数据库连接池预热失败（服务仍可启动）: {e}")
    yield
    # 清理资源
    db = get_db_service()
    await db.close()
    # 清理 Redis 连接
    try:
        from app.services.session import get_session_service

        session_svc = get_session_service()
        await session_svc.close()
    except Exception:
        pass
    logger.info("水务AI多智能体服务关闭")


# ─────────────────────────────────────────────
# FastAPI 应用
# ─────────────────────────────────────────────

app = FastAPI(
    title="水务AI多智能体防洪应急预案系统",
    description="基于 LangGraph 的多智能体协作防洪应急预案生成与执行系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# 路由
# ─────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@app.post("/api/v1/flood/query", response_model=FloodQueryResponse)
async def flood_query(request: FloodQueryRequest):
    """
    防洪应急查询 — 多智能体协作处理

    根据用户的自然语言请求，自动调度多个智能体完成：
    - 数据采集与分析
    - 风险评估
    - 预案生成
    - 资源调度
    - 通知方案

    示例请求：
    - "分析当前水情数据"
    - "评估洪水风险等级"
    - "生成防洪应急预案"
    - "制定完整的防洪应急响应方案"
    """
    session_id = request.session_id or str(uuid.uuid4())

    logger.info(f"[{session_id}] 收到查询: {request.query}")

    # 加载会话历史（best-effort）
    chat_history: list[dict] = []
    try:
        from app.services.session import get_session_service

        session_svc = get_session_service()
        chat_history = await session_svc.get_history(session_id)
    except Exception as hist_err:
        logger.debug(f"[{session_id}] 加载会话历史失败: {hist_err}")

    # 构建初始状态
    initial_state: FloodResponseState = {
        "session_id": session_id,
        "user_query": request.query,
        "messages": [],
        "chat_history": chat_history,
        "iteration": 0,
    }

    try:
        # 运行多智能体图
        final_state = await flood_response_graph.ainvoke(
            initial_state,
            config={"recursion_limit": 30},
        )

        # 提取结果
        risk = final_state.get("risk_assessment")
        plan = final_state.get("emergency_plan")

        response = FloodQueryResponse(
            session_id=session_id,
            response=final_state.get("final_response", "处理完成，但未生成完整响应"),
            risk_level=risk.risk_level.value if risk else None,
            risk_score=risk.risk_score if risk else None,
            plan_id=plan.plan_id if plan else None,
            plan_name=plan.plan_name if plan else None,
            actions_count=len(plan.actions) if plan else 0,
            resources_count=len(final_state.get("resource_plan", [])),
            notifications_count=len(final_state.get("notifications", [])),
        )

        logger.info(f"[{session_id}] 查询完成, 风险等级={response.risk_level}")

        # Best-effort 持久化（不阻塞响应）
        try:
            if plan and plan.plan_id:
                db = get_db_service()
                await db.save_emergency_plan(
                    plan_id=plan.plan_id,
                    plan_name=plan.plan_name,
                    risk_level=risk.risk_level.value if risk else "none",
                    trigger_conditions=plan.trigger_conditions,
                    status=plan.status.value,
                    session_id=session_id,
                    summary=plan.summary,
                    actions=[a.model_dump() for a in plan.actions],
                )
                resource_plan = final_state.get("resource_plan", [])
                if resource_plan:
                    await db.save_resource_allocations(
                        plan_id=plan.plan_id,
                        resources=[r.model_dump() for r in resource_plan],
                    )
                notifications = final_state.get("notifications", [])
                if notifications:
                    await db.save_notifications(
                        plan_id=plan.plan_id,
                        notifications=[n.model_dump() for n in notifications],
                    )
        except Exception as persist_err:
            logger.warning(f"[{session_id}] 预案持久化失败（不影响响应）: {persist_err}")

        # 保存会话记录到 Redis（best-effort）
        try:
            from app.services.session import get_session_service

            session_svc = get_session_service()
            await session_svc.save_turn(session_id, "user", request.query)
            await session_svc.save_turn(session_id, "assistant", response.response[:2000])
        except Exception as session_err:
            logger.debug(f"[{session_id}] 会话保存失败: {session_err}")

        return response

    except Exception as e:
        logger.exception(f"[{session_id}] 查询处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@app.post("/api/v1/flood/query/stream")
async def flood_query_stream(request: FloodQueryRequest):
    """
    防洪应急查询（流式） — 实时返回各智能体的工作进展

    使用 Server-Sent Events (SSE) 流式返回，与前端 useSSE.ts 对齐。

    事件类型：
    - session_init: 会话初始化（第一个事件）
    - agent_update: 智能体状态更新 (active | done | failed)
    - risk_update: 风险评估完成
    - plan_update: 预案生成/更新
    """
    from fastapi.responses import StreamingResponse
    import json

    session_id = request.session_id or str(uuid.uuid4())

    async def event_stream():
        initial_state: FloodResponseState = {
            "session_id": session_id,
            "user_query": request.query,
            "messages": [],
            "iteration": 0,
        }

        # 发送 session_init 事件
        yield f"data: {json.dumps({'type': 'session_init', 'sessionId': session_id}, ensure_ascii=False)}\n\n"

        def _extract_agent_messages(node_name: str, node_output: dict) -> list[dict]:
            """从节点输出中提取 agent_message 事件列表。

            对于 parallel_dispatch，resource_dispatcher 和 notification 各自的文字
            都保留在 node_output["messages"] 里（通过 merged["messages"].extend 拼入）。
            其余节点直接取 messages 列表最后一条非 parallel_dispatch role 的内容。
            """
            events: list[dict] = []
            messages: list[dict] = node_output.get("messages", [])

            if node_name == "parallel_dispatch":
                # messages 中包含来自 resource_dispatcher 和 notification 的各自条目
                for msg in messages:
                    role = msg.get("role", "")
                    content = msg.get("content", "").strip()
                    if role in ("resource_dispatcher", "notification") and content:
                        events.append(
                            {
                                "type": "agent_message",
                                "agent": role,
                                "content": content,
                            }
                        )
            elif node_name != "supervisor" and messages:
                # 取该节点自己的最后一条消息
                content = messages[-1].get("content", "").strip()
                if content:
                    events.append(
                        {
                            "type": "agent_message",
                            "agent": node_name,
                            "content": content,
                        }
                    )
            return events

        try:
            async for event in flood_response_graph.astream(initial_state, stream_mode="updates"):
                for node_name, node_output in event.items():
                    # 1. 非 supervisor 节点先发 active 事件
                    if node_name != "supervisor":
                        yield f"data: {json.dumps({'type': 'agent_update', 'agent': node_name, 'status': 'active'}, ensure_ascii=False)}\n\n"

                    # 2. 节点完成事件（附带关键数据）
                    done_event: dict = {
                        "type": "agent_update",
                        "agent": node_name,
                        "status": "done",
                    }
                    if node_name == "supervisor":
                        done_event["next_agent"] = node_output.get("next_agent", "")
                    elif node_name == "data_analyst":
                        done_event["data_summary_length"] = len(node_output.get("data_summary", ""))
                    elif node_name == "risk_assessor":
                        ra = node_output.get("risk_assessment")
                        if ra:
                            done_event["risk_level"] = ra.risk_level.value
                            done_event["risk_score"] = ra.risk_score
                    elif node_name == "plan_generator":
                        plan = node_output.get("emergency_plan")
                        if plan:
                            done_event["plan_id"] = plan.plan_id
                            done_event["actions_count"] = len(plan.actions)
                    elif node_name == "final_response":
                        done_event["response"] = node_output.get("final_response", "")

                    yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"

                    # 3. agent_message 事件：每个 agent 的完整文字输出
                    for msg_event in _extract_agent_messages(node_name, node_output):
                        yield f"data: {json.dumps(msg_event, ensure_ascii=False)}\n\n"

                    # 4. 附加结构化事件（与前端 SSEEventType 对齐）

                    # risk_update
                    if node_name == "risk_assessor":
                        ra = node_output.get("risk_assessment")
                        if ra:
                            risk_event = {
                                "type": "risk_update",
                                "level": ra.risk_level.value,
                                "details": ra.key_risks[:5],
                            }
                            yield f"data: {json.dumps(risk_event, ensure_ascii=False)}\n\n"

                    # plan_update
                    if node_name in ("plan_generator", "parallel_dispatch", "execution_monitor"):
                        plan = node_output.get("emergency_plan")
                        if plan and plan.plan_id:
                            prog = node_output.get("execution_progress")
                            plan_event = {
                                "type": "plan_update",
                                "name": plan.plan_name,
                                "status": plan.status.value,
                                "total": prog.total_actions if prog else len(plan.actions),
                                "completed": prog.completed_actions if prog else 0,
                                "failed": prog.failed_actions if prog else 0,
                            }
                            yield f"data: {json.dumps(plan_event, ensure_ascii=False)}\n\n"

            # 完成信号
            yield f"data: {json.dumps({'type': 'agent_update', 'agent': '__done__', 'status': 'done', 'sessionId': session_id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'agent_update', 'agent': '__error__', 'status': 'failed', 'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ─────────────────────────────────────────────
# 预案管理 API
# ─────────────────────────────────────────────


async def _do_execute_plan(plan_id: str, actions: list[dict]) -> None:
    """
    后台执行预案（不阻塞 HTTP 响应）

    方案二 — 措施状态追踪：
        逐条将 emergency_action.status 从 pending → in_progress → completed/failed

    方案三 — 告警联动：
        遇到 notification 类型措施时，自动 ACK 平台上的活跃告警，
        表明系统已知晓并进入响应状态。
    """
    db = get_db_service()
    platform = get_platform_client()
    failed_count = 0

    for action in actions:
        action_id = action.get("action_id", "")
        action_type = action.get("action_type", "")
        try:
            # 标记为执行中（方案二）
            await db.update_action_status(plan_id, action_id, "in_progress")

            # 告警联动：通知类措施触发活跃告警 ACK（方案三）
            if action_type == "notification":
                try:
                    active_alarms = await db.get_active_alarms()
                    ack_count = 0
                    for alarm in active_alarms[:10]:  # 限制最多处理 10 条，避免瞬时大量请求
                        await platform.acknowledge_alarm(str(alarm["id"]))
                        ack_count += 1
                    logger.info(f"[{plan_id}] 告警联动：已 ACK {ack_count} 条活跃告警")
                except Exception as alarm_err:
                    logger.warning(f"[{plan_id}] 告警联动失败（不影响预案执行）: {alarm_err}")

            # 标记为完成（方案二）
            await db.update_action_status(plan_id, action_id, "completed")
        except Exception as action_err:
            logger.warning(f"[{plan_id}] 措施 {action_id} 执行失败: {action_err}")
            try:
                await db.update_action_status(plan_id, action_id, "failed")
            except Exception:
                pass
            failed_count += 1

    # 全部措施完成后更新预案最终状态
    final_status = "completed" if failed_count == 0 else "executing"
    await db.update_plan_status(plan_id, final_status)
    logger.info(
        f"[{plan_id}] 后台执行完成：共 {len(actions)} 项措施，失败 {failed_count} 项，最终状态 → {final_status}"
    )


class PlanDetailResponse(BaseModel):
    """预案详情响应"""

    plan_id: str
    plan_name: str
    risk_level: str
    trigger_conditions: str
    status: str
    session_id: str
    summary: str
    actions: list[dict]
    resources: list[dict]
    notifications: list[dict]
    created_at: str | None = None


class PlanExecuteRequest(BaseModel):
    """预案执行请求"""

    action_ids: list[str] | None = None  # 指定执行哪些措施，为空则执行全部


class PlanExecuteResponse(BaseModel):
    """预案执行响应"""

    plan_id: str
    status: str
    executed_actions: int
    message: str


@app.get("/api/v1/plans", response_model=list[dict])
async def list_plans(limit: int = 20, offset: int = 0):
    """获取预案列表"""
    try:
        db = get_db_service()
        plans = await db.get_plans(limit, offset)
        return plans
    except Exception as e:
        logger.error(f"获取预案列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/plans/count")
async def get_plan_count():
    """获取预案总数"""
    try:
        db = get_db_service()
        count = await db.get_plan_count()
        return {"count": count}
    except Exception as e:
        logger.error(f"获取预案总数失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/plans/{plan_id}", response_model=PlanDetailResponse)
async def get_plan(plan_id: str):
    """获取预案详情"""
    try:
        db = get_db_service()
        plan = await db.get_emergency_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="预案不存在")

        actions = await db.get_plan_actions(plan_id)
        resources = await db.get_plan_resources(plan_id)
        notifications = await db.get_plan_notifications(plan_id)

        return PlanDetailResponse(
            plan_id=plan["plan_id"],
            plan_name=plan["plan_name"],
            risk_level=plan["risk_level"],
            trigger_conditions=plan["trigger_conditions"],
            status=plan["status"],
            session_id=plan["session_id"],
            summary=plan["summary"],
            actions=actions,
            resources=resources,
            notifications=notifications,
            created_at=str(plan.get("created_at", "")) if plan.get("created_at") else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取预案详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/plans/{plan_id}/execute", response_model=PlanExecuteResponse)
async def execute_plan(plan_id: str, background_tasks: BackgroundTasks, request: PlanExecuteRequest = None):
    """执行预案"""
    try:
        db = get_db_service()
        plan = await db.get_emergency_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="预案不存在")

        # 获取要执行的动作
        actions = await db.get_plan_actions(plan_id)
        if request and request.action_ids:
            actions_to_execute = [a for a in actions if a.get("action_id") in request.action_ids]
        else:
            actions_to_execute = actions

        # 更新预案状态为执行中
        await db.update_plan_status(plan_id, "executing")

        # 方案四a：BackgroundTasks 异步后台执行，立即返回响应
        background_tasks.add_task(_do_execute_plan, plan_id, actions_to_execute)
        executed_count = len(actions_to_execute)

        logger.info(f"预案 {plan_id} 已提交后台执行，共 {executed_count} 项措施")

        return PlanExecuteResponse(
            plan_id=plan_id,
            status="executing",
            executed_actions=executed_count,
            message=f"预案已开始执行，共 {executed_count} 项措施",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行预案失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/plans/{plan_id}")
async def delete_plan(plan_id: str):
    """删除预案"""
    try:
        db = get_db_service()
        plan = await db.get_emergency_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="预案不存在")

        # 物理删除（cascade会删除关联的actions, resources, notifications）
        pool = await db._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM emergency_plan WHERE plan_id = $1", plan_id)

        return {"message": "预案已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除预案失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# 会话历史 API
# ─────────────────────────────────────────────


class SessionResponse(BaseModel):
    """会话响应"""

    session_id: str
    plans: list[dict]
    created_at: str | None = None


@app.get("/api/v1/sessions", response_model=list[dict])
async def list_sessions(limit: int = 20, offset: int = 0):
    """获取会话列表"""
    try:
        db = get_db_service()
        sessions = await db.get_sessions(limit, offset)
        return sessions
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sessions/count")
async def get_session_count():
    """获取会话总数"""
    try:
        db = get_db_service()
        count = await db.get_session_count()
        return {"count": count}
    except Exception as e:
        logger.error(f"获取会话总数失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """获取会话详情（包括相关预案）"""
    try:
        db = get_db_service()
        plans = await db.get_plans_by_session(session_id)

        if not plans:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 获取最早创建的预案时间作为会话创建时间
        created_at = plans[0].get("created_at") if plans else None

        return SessionResponse(
            session_id=session_id,
            plans=plans,
            created_at=str(created_at) if created_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# 启动入口
# ─────────────────────────────────────────────


def main():
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.ai_service_host,
        port=settings.ai_service_port,
        reload=True,
    )


if __name__ == "__main__":
    main()
