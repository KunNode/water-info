"""Supervisor routing node."""

from __future__ import annotations

import hashlib
import json
import re

from pydantic import BaseModel, Field

from app.config import get_settings
from app.platform.skill_executor import SkillExecutor
from app.platform.skill_registry import get_skill_registry
from app.schemas.routing import RoutingDecision, SafetyLevel
from app.services.llm import get_llm
from app.state import RiskLevel
from app.tools.trace import make_trace
from app.utils.json_parser import extract_json

_RAG_GROUNDING_RISK = {RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL}


def _normalize_query_hash(query: str) -> str:
    return hashlib.sha1(query.strip().lower().encode("utf-8")).hexdigest()


def _risk_level_value(state: dict) -> RiskLevel:
    assessment = state.get("risk_assessment")
    if not assessment:
        return RiskLevel.NONE
    level = getattr(assessment, "risk_level", None)
    if isinstance(level, RiskLevel):
        return level
    try:
        return RiskLevel(level)
    except Exception:
        return RiskLevel.NONE


def _should_invoke_rag(state: dict, deterministic_next: str | None) -> tuple[str, str] | None:
    """Decide whether to slot knowledge_retriever ahead of the planned next agent.

    Returns (rag_target, reason) when RAG should run, otherwise None.
    """
    settings = get_settings()
    query = str(state.get("user_query", "")).strip()
    if not query:
        return None

    # Budget cap: limit retrieval traffic per session.
    if int(state.get("rag_call_count", 0)) >= settings.rag_max_calls_per_session:
        return None

    # In-session cache: skip if this exact query was already retrieved.
    query_hash = _normalize_query_hash(query)
    if query_hash in (state.get("rag_query_cache") or {}):
        return None

    intent = str(state.get("intent") or "")

    # Mode: direct knowledge Q&A (manuals/regulations/...).
    if intent == "knowledge_qa" or deterministic_next == "knowledge_retriever":
        return "answer", "intent=knowledge_qa"

    has_evidence = bool(state.get("evidence_context"))
    if has_evidence:
        return None

    # Mode: preflight grounding for plan generation when stakes are non-trivial.
    if deterministic_next == "plan_generator" and _risk_level_value(state) in _RAG_GROUNDING_RISK:
        return "preflight_plan", "preflight grounding for plan_generator (risk>=moderate)"

    # Optional preflight for risk_assessor when query mentions regulations.
    if (
        settings.rag_preflight_risk_enabled
        and deterministic_next == "risk_assessor"
        and _is_knowledge_query(query)
    ):
        return "preflight_risk", "preflight grounding for risk_assessor (regulation-tagged query)"

    return None


class SupervisorDecision(BaseModel):
    next_agent: str = Field(
        pattern=(
            "^(conversation_assistant|data_analyst|risk_assessor|plan_generator|resource_dispatcher|"
            "notification|execution_monitor|parallel_dispatch|knowledge_retriever|plan_reviewer|safety_checker|__end__)$"
        )
    )
    reasoning: str
    intent: str | None = None
    focus_station_query: str | None = None


EXECUTION_KEYWORDS = ["执行", "进度", "完成了吗", "落实", "落地", "推进到哪", "执行情况"]
PLAN_KEYWORDS = ["预案", "方案", "怎么处置", "怎么应对", "响应", "处置方案", "行动建议"]
RESOURCE_KEYWORDS = ["资源", "物资", "调度", "队伍", "人员", "车辆", "抢险力量", "装备"]
NOTIFICATION_KEYWORDS = ["通知", "告知", "通报", "谁需要知道", "通知谁", "发送给谁"]
RISK_KEYWORDS = ["风险", "研判", "评估", "危险吗", "严不严重", "趋势判断"]
ALARM_KEYWORDS = ["告警", "预警", "报警", "异常", "超限", "告急"]
OVERVIEW_KEYWORDS = ["总览", "概况", "整体", "总体", "全局", "态势", "情况怎么样", "现在怎么样", "总体情况"]
STATION_KEYWORDS = ["站", "站点", "水库", "闸", "泵站", "断面"]
DATA_ONLY_KEYWORDS = ["无需分析", "不用分析", "不要分析", "无须分析", "只要数据", "只看数据", "数据库数据"]
DATA_LOOKUP_KEYWORDS = ["最新", "数据", "观测", "记录", "明细"]
KNOWLEDGE_KEYWORDS = [
    "制度",
    "手册",
    "规范",
    "条例",
    "办法",
    "流程",
    "规程",
    "值班要求",
    "预案模板",
    "文档",
    "资料",
    "文件",
    "依据",
]
WATER_DOMAIN_KEYWORDS = [
    *STATION_KEYWORDS,
    "水情",
    "水位",
    "雨量",
    "洪水",
    "防汛",
    "河道",
    "监测",
    *ALARM_KEYWORDS,
    "应急",
    *RISK_KEYWORDS,
    *PLAN_KEYWORDS,
    *RESOURCE_KEYWORDS,
    *NOTIFICATION_KEYWORDS,
    *EXECUTION_KEYWORDS,
]
HIGH_RISK_ACTION_KEYWORDS = ["疏散", "撤离", "封路", "道路封闭", "停运", "停课", "停工", "服务暂停"]
ELEVATED_ACTION_KEYWORDS = ["响应升级", "提升响应", "外部通知", "发布通知", "调度", "派遣"]


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _extract_requested_count(query: str) -> int:
    for pattern in [r"最新(?:的)?\s*(\d{1,3})\s*条", r"(\d{1,3})\s*条"]:
        match = re.search(pattern, query)
        if match:
            return max(1, min(int(match.group(1)), 50))
    return 1


def _infer_metric_type(query: str) -> str | None:
    if any(word in query for word in ["水位", "水深"]):
        return "WATER_LEVEL"
    if any(word in query for word in ["雨量", "降雨", "雨情"]):
        return "RAINFALL"
    if any(word in query for word in ["流量", "流速"]):
        return "FLOW"
    return None


def _infer_answer_policy(query: str) -> dict:
    data_only = _contains_any(query, DATA_ONLY_KEYWORDS)
    data_lookup = data_only or (
        _contains_any(query, DATA_LOOKUP_KEYWORDS)
        and ("最新" in query or "数据库" in query or "数据" in query)
    )
    requested_count = _extract_requested_count(query)
    return {
        "data_only": data_only,
        "data_lookup": data_lookup,
        "requested_count": requested_count,
        "metric_type": _infer_metric_type(query),
        "suppress_risk": data_only,
        "suppress_summary": data_only,
    }


def _is_general_chat_query(query: str) -> bool:
    lowered = query.strip().lower()
    if not lowered:
        return True
    if re.match(r"^(你好|您好|hi|hello|hey|嗨|哈喽|在吗|在不在|你是谁)", lowered):
        return True
    return _contains_any(
        query,
        [
            "你能做什么",
            "怎么用",
            "帮助",
            "help",
            "介绍一下你自己",
            "你是谁",
            "谢谢",
            "辛苦了",
            "再见",
        ],
    )


def _is_water_domain_query(query: str) -> bool:
    return _contains_any(query, WATER_DOMAIN_KEYWORDS)


def _is_knowledge_query(query: str) -> bool:
    return _contains_any(query, KNOWLEDGE_KEYWORDS)


def _is_alarm_overview_query(query: str, *, has_station_focus: bool) -> bool:
    has_alarm = _contains_any(query, ALARM_KEYWORDS)
    has_overview = _contains_any(query, OVERVIEW_KEYWORDS + ["分布", "多少", "有哪些", "哪里", "集中在哪"])
    if has_station_focus:
        return False
    return has_alarm and (has_overview or "告警" in query or "预警" in query)


def _infer_intent(query: str) -> str:
    has_station_focus = _infer_focus_station_query(query) is not None or _contains_any(query, STATION_KEYWORDS)
    if _is_general_chat_query(query):
        return "general_chat"
    if _infer_answer_policy(query)["data_lookup"]:
        return "station_status" if has_station_focus else "overview"
    if _is_knowledge_query(query):
        return "knowledge_qa"
    if _contains_any(query, EXECUTION_KEYWORDS):
        return "execution_status"
    if _contains_any(query, RESOURCE_KEYWORDS):
        return "resource_dispatch"
    if _contains_any(query, NOTIFICATION_KEYWORDS):
        return "notification"
    if _contains_any(query, PLAN_KEYWORDS):
        return "plan_generation"
    if _contains_any(query, RISK_KEYWORDS):
        return "risk_assessment"
    if has_station_focus:
        return "station_status"
    if _is_alarm_overview_query(query, has_station_focus=has_station_focus):
        return "alarm_overview"
    if _contains_any(query, OVERVIEW_KEYWORDS) and _is_water_domain_query(query):
        return "overview"
    if _is_water_domain_query(query):
        return "overview"
    return "general_chat"


def _infer_focus_station_query(query: str) -> str | None:
    for pattern in [
        r"([A-Za-z0-9\-_]{2,})站点",
        r"站点([A-Za-z0-9\u4e00-\u9fa5\-_]{2,12})",
        r"([A-Za-z0-9\u4e00-\u9fa5\-_]{2,12})(?:站|水库|闸|泵站|断面)",
    ]:
        match = re.search(pattern, query)
        if match:
            return match.group(1)
    return None


def _infer_safety_level(query: str, next_agent: str) -> SafetyLevel:
    if _contains_any(query, HIGH_RISK_ACTION_KEYWORDS):
        return SafetyLevel.CRITICAL
    if next_agent in {"resource_dispatcher", "notification"} or _contains_any(query, ELEVATED_ACTION_KEYWORDS):
        return SafetyLevel.HIGH
    if next_agent in {"plan_generator", "risk_assessor", "parallel_dispatch"}:
        return SafetyLevel.ELEVATED
    return SafetyLevel.NORMAL


def _required_context_for_agent(next_agent: str) -> list[str]:
    requirements = {
        "data_analyst": ["user_query"],
        "risk_assessor": ["data_summary"],
        "plan_generator": ["risk_assessment", "evidence_context"],
        "resource_dispatcher": ["emergency_plan"],
        "notification": ["emergency_plan"],
        "execution_monitor": ["session_id"],
        "knowledge_retriever": ["user_query"],
    }
    return requirements.get(next_agent, [])


def _missing_context_for_agent(next_agent: str, state: dict, required_context: list[str]) -> list[str]:
    missing: list[str] = []
    for field in required_context:
        if field == "evidence_context":
            continue
        if not state.get(field):
            missing.append(field)
    if next_agent == "__end__":
        return []
    return missing


def _with_structured_routing(update: dict, state: dict, user_query: str) -> dict:
    if not get_settings().structured_output_enabled:
        return update

    next_agent = str(update.get("next_agent") or "__end__")
    intent = str(update.get("intent") or state.get("intent") or _infer_intent(user_query))
    required_context = _required_context_for_agent(next_agent)
    missing_context = _missing_context_for_agent(next_agent, {**state, **update}, required_context)
    safety_level = SafetyLevel.HIGH if update.get("human_confirmation_required") else _infer_safety_level(user_query, next_agent)
    decision = RoutingDecision(
        intent=intent,
        next_agent=next_agent,
        required_context=required_context,
        missing_context=missing_context,
        reasoning=str(update.get("supervisor_reasoning") or "structured routing"),
        safety_level=safety_level,
    )

    enriched = dict(update)
    enriched["agent_run_id"] = decision.agent_run_id
    enriched["routing_decision"] = decision.model_dump(mode="json")
    enriched["safety_level"] = decision.safety_level.value
    enriched["human_confirmation_required"] = bool(update.get("human_confirmation_required")) or decision.human_confirmation_required
    return enriched


def _deterministic_route(state: dict) -> str | None:
    query = str(state.get("user_query", ""))
    intent = str(state.get("intent") or _infer_intent(query))
    answer_policy = state.get("answer_policy") or _infer_answer_policy(query)
    has_data = bool(state.get("data_summary"))
    has_risk = state.get("risk_assessment") is not None
    has_plan = state.get("emergency_plan") is not None
    has_resources = bool(state.get("resource_plan"))
    has_notifications = bool(state.get("notifications"))
    mentions_data = _contains_any(query, ["水情", "监测", "数据", "态势", "分析", *OVERVIEW_KEYWORDS])
    mentions_risk = _contains_any(query, RISK_KEYWORDS)
    mentions_plan = _contains_any(query, PLAN_KEYWORDS)
    mentions_resource = _contains_any(query, RESOURCE_KEYWORDS)
    mentions_notification = _contains_any(query, NOTIFICATION_KEYWORDS)

    if not has_data:
        if intent == "knowledge_qa":
            return "knowledge_retriever"
        if intent == "general_chat":
            return "conversation_assistant"
        return "data_analyst"
    if answer_policy.get("data_only"):
        return "__end__"
    if intent == "general_chat":
        return "conversation_assistant"
    if intent == "knowledge_qa":
        return "knowledge_retriever"
    if intent == "station_status":
        if not has_risk:
            return "risk_assessor"
        return "__end__"
    if intent == "overview":
        if not has_risk:
            return "risk_assessor"
        return "__end__"
    if intent == "alarm_overview":
        if not has_risk:
            return "risk_assessor"
        return "__end__"
    if intent == "risk_assessment":
        if not has_risk:
            return "risk_assessor"
        if mentions_plan and not has_plan:
            return "plan_generator"
        return "__end__"
    if intent == "execution_status":
        return "execution_monitor"
    if intent == "resource_dispatch":
        if not has_risk:
            return "risk_assessor"
        if not has_plan:
            return "plan_generator"
        if not has_resources:
            return "resource_dispatcher"
        return "__end__"
    if intent == "notification":
        if not has_risk:
            return "risk_assessor"
        if not has_plan:
            return "plan_generator"
        if not has_notifications:
            return "notification"
        return "__end__"
    if intent == "plan_generation":
        if not has_risk:
            return "risk_assessor"
        if not has_plan:
            return "plan_generator"
        if not has_resources:
            return "resource_dispatcher"
        if not has_notifications:
            return "notification"
        return "__end__"
    if mentions_risk and not has_risk:
        return "risk_assessor"
    if mentions_plan and not has_risk:
        return "risk_assessor"
    if mentions_plan and has_risk and not has_plan:
        return "plan_generator"
    if mentions_resource and has_plan and not has_resources:
        return "resource_dispatcher"
    if mentions_notification and has_plan and not has_notifications:
        return "notification"
    if has_data and has_risk and has_plan and has_resources and has_notifications:
        return "__end__"
    if mentions_data:
        return "__end__" if has_data else "data_analyst"
    return None


def _agent_completed(agent: str, state: dict) -> bool:
    if agent == "data_analyst":
        return bool(state.get("data_summary"))
    if agent == "risk_assessor":
        return state.get("risk_assessment") is not None
    if agent == "plan_generator":
        return state.get("emergency_plan") is not None
    if agent == "resource_dispatcher":
        return bool(state.get("resource_plan"))
    if agent == "notification":
        return bool(state.get("notifications"))
    if agent == "plan_reviewer":
        return state.get("compliance_result") is not None
    if agent == "safety_checker":
        return state.get("safety_check_result") is not None
    if agent == "execution_monitor":
        return state.get("execution_progress") is not None
    return False


def _skill_route(state: dict, intent: str) -> dict | None:
    settings = get_settings()
    if not settings.skill_registry_enabled:
        return None
    registry = get_skill_registry()
    if not registry.skills:
        registry.load_all()
    skill = registry.lookup_by_intent(intent)
    if skill is None:
        return None
    sequence = list(state.get("skill_agent_sequence") or skill.agent_sequence)
    for agent in sequence:
        if not _agent_completed(agent, state):
            return {
                "next_agent": agent,
                "active_skill_id": skill.id,
                "skill_agent_sequence": sequence,
                "allowed_tools": list(skill.required_tools),
                "supervisor_reasoning": f"skill route: {skill.id}",
            }
    quality_results = SkillExecutor().evaluate_quality_gates(skill, state)
    quality_payload = [item.model_dump(mode="json") for item in quality_results]
    failed = [item for item in quality_results if not item.passed]
    if failed and skill.fallback_strategy == "retry":
        next_agent = sequence[0] if sequence else "__end__"
    elif failed and skill.fallback_strategy == "escalate_to_human":
        next_agent = "__end__"
    else:
        next_agent = "__end__"
    update = {
        "next_agent": next_agent,
        "active_skill_id": skill.id,
        "skill_agent_sequence": sequence,
        "skill_quality_results": quality_payload,
        "allowed_tools": list(skill.required_tools),
        "supervisor_reasoning": f"skill complete: {skill.id}",
    }
    if failed and skill.fallback_strategy == "escalate_to_human":
        update["human_confirmation_required"] = True
        update["pending_approvals"] = [{
            "action_type": "quality_gate_failure",
            "action_payload": {"skill_id": skill.id, "failed_gates": quality_payload},
            "status": "pending",
        }]
        update["supervisor_reasoning"] = f"skill quality gate failed: {skill.id}"
    elif failed:
        update["supervisor_reasoning"] = f"skill quality gate failed: {skill.id}; fallback={skill.fallback_strategy}"
    return update


def _guard_model_route(next_agent: str, state: dict, deterministic: str | None) -> tuple[str, str | None]:
    """Keep LLM routing as the primary path while enforcing workflow preconditions."""
    has_data = bool(state.get("data_summary"))
    has_risk = state.get("risk_assessment") is not None
    has_plan = state.get("emergency_plan") is not None
    has_resources = bool(state.get("resource_plan"))
    has_notifications = bool(state.get("notifications"))

    if next_agent in {"conversation_assistant", "knowledge_retriever", "execution_monitor"}:
        return next_agent, None

    if next_agent == "__end__":
        if deterministic and deterministic != "__end__":
            return deterministic, "guarded: workflow still has a required next step"
        return next_agent, None

    if not has_data:
        return deterministic or "data_analyst", "guarded: data grounding is required first"

    if next_agent == "data_analyst" and has_data:
        return deterministic or "__end__", "guarded: data analysis is already complete"

    if next_agent == "risk_assessor" and has_risk:
        return deterministic or "__end__", "guarded: risk assessment is already complete"

    if next_agent == "plan_generator" and has_plan:
        return deterministic or "__end__", "guarded: emergency plan is already complete"

    if next_agent == "resource_dispatcher" and has_resources:
        return deterministic or "__end__", "guarded: resource dispatch is already complete"

    if next_agent == "notification" and has_notifications:
        return deterministic or "__end__", "guarded: notifications are already complete"

    if next_agent in {"plan_generator", "resource_dispatcher", "notification", "parallel_dispatch"} and not has_risk:
        return deterministic or "risk_assessor", "guarded: risk assessment is required before planning/dispatch"

    if next_agent in {"resource_dispatcher", "notification", "parallel_dispatch"} and not has_plan:
        return deterministic or "plan_generator", "guarded: emergency plan is required before dispatch/notification"

    return next_agent, None


def _rag_preempt(
    next_agent: str,
    state: dict,
    deterministic: str | None,
    inferred_intent: str,
    inferred_focus_station: str | None,
    iteration: int,
    base_reasoning: str,
) -> dict | None:
    """If the RAG gate fires for the planned next agent, redirect to knowledge_retriever."""
    if next_agent in {"__end__", "conversation_assistant", "execution_monitor", "knowledge_retriever"}:
        if next_agent != "knowledge_retriever":
            return None
    decision = _should_invoke_rag(state, next_agent)
    if not decision:
        return None
    rag_target, reason = decision
    return {
        "next_agent": "knowledge_retriever",
        "rag_target": rag_target,
        "iteration": iteration,
        "current_agent": "supervisor",
        "intent": inferred_intent,
        "focus_station_query": inferred_focus_station,
        "supervisor_reasoning": f"{base_reasoning}; rag-gate: {reason}",
    }


async def supervisor_node(state: dict) -> dict:
    iteration = int(state.get("iteration", 0)) + 1
    if iteration > 8:
        update = {"next_agent": "__end__", "iteration": iteration, "current_agent": "supervisor"}
        return _with_structured_routing(update, state, str(state.get("user_query", "")))
    if state.get("error"):
        update = {"next_agent": "__end__", "iteration": iteration, "current_agent": "supervisor"}
        return _with_structured_routing(update, state, str(state.get("user_query", "")))

    user_query = str(state.get("user_query", ""))
    inferred_intent = str(state.get("intent") or _infer_intent(user_query))
    inferred_focus_station = state.get("focus_station_query") or _infer_focus_station_query(user_query)
    answer_policy = state.get("answer_policy") or _infer_answer_policy(user_query)

    traces: list[dict] = [
        make_trace(
            phase="data_query",
            title=f"意图识别: {inferred_intent}",
            detail=f"焦点站点: {inferred_focus_station}" if inferred_focus_station else "",
        ),
    ]

    if answer_policy.get("data_only"):
        traces.append(make_trace(
            phase="data_query",
            title="检测到纯数据查询，跳过风险评估",
        ))

    # General chat should not be handed back to the workflow planner just because
    # an LLM is available; otherwise simple greetings can drift into analysis.
    if inferred_intent == "general_chat" and not _is_water_domain_query(user_query):
        return _with_structured_routing({
            "next_agent": "conversation_assistant",
            "iteration": iteration,
            "current_agent": "supervisor",
            "intent": inferred_intent,
            "focus_station_query": inferred_focus_station,
            "answer_policy": answer_policy,
            "supervisor_reasoning": "general chat hard route",
            "execution_traces": traces,
        }, state, user_query)

    llm = get_llm()
    deterministic = _deterministic_route(state)
    skill_update = _skill_route(state, inferred_intent)
    if skill_update is not None:
        next_agent = str(skill_update["next_agent"])
        preempt = _rag_preempt(
            next_agent,
            state,
            deterministic,
            inferred_intent,
            inferred_focus_station,
            iteration,
            str(skill_update.get("supervisor_reasoning") or "skill route"),
        )
        update = preempt or skill_update
        update.update({
            "iteration": iteration,
            "current_agent": "supervisor",
            "intent": inferred_intent,
            "focus_station_query": inferred_focus_station,
            "answer_policy": answer_policy,
            "execution_traces": traces,
        })
        return _with_structured_routing(update, state, user_query)
    if deterministic == "__end__" and (
        state.get("risk_assessment") is not None
        or state.get("emergency_plan") is not None
        or bool(state.get("resource_plan"))
        or bool(state.get("notifications"))
    ):
        traces.append(make_trace(
            phase="final_response",
            title="工作流完成，准备生成最终回答",
        ))
        return _with_structured_routing({
            "next_agent": "__end__",
            "iteration": iteration,
            "current_agent": "supervisor",
            "intent": inferred_intent,
            "focus_station_query": inferred_focus_station,
            "answer_policy": answer_policy,
            "supervisor_reasoning": "deterministic complete",
            "execution_traces": traces,
        }, state, user_query)

    # When LLM is unavailable, fall back to deterministic routing immediately.
    if not llm.is_enabled:
        next_agent = deterministic or "__end__"
        preempt = _rag_preempt(
            next_agent, state, deterministic, inferred_intent, inferred_focus_station,
            iteration, "deterministic (no llm)",
        )
        if preempt:
            return _with_structured_routing(preempt, state, user_query)
        return _with_structured_routing({
            "next_agent": next_agent,
            "iteration": iteration,
            "current_agent": "supervisor",
            "intent": inferred_intent,
            "focus_station_query": inferred_focus_station,
            "answer_policy": answer_policy,
            "supervisor_reasoning": "deterministic (no llm)",
            "execution_traces": traces,
        }, state, user_query)

    prompt = json.dumps({
        "query": state.get("user_query", ""),
        "iteration": iteration,
        "intent_hint": inferred_intent,
        "focus_station_hint": inferred_focus_station,
        "workflow_state": {
            "data_summary": bool(state.get("data_summary")),
            "risk_assessment": bool(state.get("risk_assessment")),
            "emergency_plan": bool(state.get("emergency_plan")),
            "resource_plan": bool(state.get("resource_plan")),
            "notifications": bool(state.get("notifications")),
        },
        "memory_context": state.get("memory_context", {}),
        "answer_policy": answer_policy,
        "guardrails": [
            "防汛业务问题必须先有 data_analyst 提供监测数据 grounding，除非是闲聊或知识库问答。",
            "预案、资源、通知必须建立在 risk_assessor 的风险评估之后。",
            "资源调度和通知必须建立在 plan_generator 的预案之后。",
            "涉及刚才、上一轮、前面说的、我叫什么等同会话上下文问题，"
            "可根据 memory_context.recent_session_messages 选择 conversation_assistant。",
            "无法判断或当前任务已完整时才选择 __end__。",
        ],
    }, ensure_ascii=False)

    parsed = None
    try:
        response = await llm.ainvoke(
            prompt,
            system_prompt=(
                "你是防汛应急多智能体系统的调度 Supervisor。"
                "你的主任务是根据用户真实意图和当前 workflow_state 选择唯一 next_agent；"
                "规则只作为安全边界，不是让你照关键词机械路由。"
                "如果用户问制度、手册、规范、流程、依据等知识内容，优先选择 knowledge_retriever。"
                "如果用户问数据/站点状态，选择 data_analyst 或在已有数据后进入 risk_assessor。"
                "如果用户要风险、预案、资源、通知，按 grounding -> risk -> plan -> dispatch/notification 的依赖推进。"
                "只返回 JSON："
                '{"next_agent":"conversation_assistant|data_analyst|risk_assessor|plan_generator|resource_dispatcher|notification|execution_monitor|parallel_dispatch|knowledge_retriever|__end__",'
                '"intent":"general_chat|knowledge_qa|station_status|overview|alarm_overview|risk_assessment|plan_generation|resource_dispatch|notification|execution_status",'
                '"focus_station_query":"站点名称或编码，可为空",'
                '"reasoning":"简短原因"}'
            ),
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        parsed = extract_json(getattr(response, "content", None))
    except Exception:
        parsed = None

    try:
        decision = SupervisorDecision.model_validate(parsed)
        next_agent, guard_reason = _guard_model_route(decision.next_agent, state, deterministic)
        intent = decision.intent or inferred_intent
        focus_station_query = decision.focus_station_query or inferred_focus_station
        reasoning = decision.reasoning if not guard_reason else f"{decision.reasoning}; {guard_reason}"
    except Exception:
        next_agent = deterministic or "__end__"
        intent = inferred_intent
        focus_station_query = inferred_focus_station
        reasoning = "deterministic fallback"

    preempt = _rag_preempt(
        next_agent, state, deterministic, intent, focus_station_query, iteration, reasoning,
    )
    if preempt:
        preempt["execution_traces"] = traces
        return _with_structured_routing(preempt, state, user_query)

    return _with_structured_routing({
        "next_agent": next_agent,
        "iteration": iteration,
        "current_agent": "supervisor",
        "intent": intent,
        "focus_station_query": focus_station_query,
        "answer_policy": answer_policy,
        "supervisor_reasoning": reasoning,
        "execution_traces": traces,
    }, state, user_query)
