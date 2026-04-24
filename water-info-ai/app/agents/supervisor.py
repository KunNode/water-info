"""Supervisor routing node."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from app.services.llm import get_llm
from app.utils.json_parser import extract_json


class SupervisorDecision(BaseModel):
    next_agent: str = Field(
        pattern=(
            "^(conversation_assistant|data_analyst|risk_assessor|plan_generator|resource_dispatcher|"
            "notification|execution_monitor|parallel_dispatch|knowledge_retriever|__end__)$"
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


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


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


def _deterministic_route(state: dict) -> str | None:
    query = str(state.get("user_query", ""))
    intent = str(state.get("intent") or _infer_intent(query))
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
    if intent == "general_chat":
        return "conversation_assistant"
    if intent == "knowledge_qa":
        return "knowledge_retriever"
    if intent == "station_status":
        if not has_risk:
            return "risk_assessor"
        return "__end__"
    if intent == "overview":
        if mentions_risk and not has_risk:
            return "risk_assessor"
        return "__end__"
    if intent == "alarm_overview":
        if mentions_risk and not has_risk:
            return "risk_assessor"
        return "__end__"
    if intent == "risk_assessment":
        return "risk_assessor" if not has_risk else "__end__"
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


def _guard_model_route(next_agent: str, state: dict, deterministic: str | None) -> tuple[str, str | None]:
    """Keep LLM routing as the primary path while enforcing workflow preconditions."""
    has_data = bool(state.get("data_summary"))
    has_risk = state.get("risk_assessment") is not None
    has_plan = state.get("emergency_plan") is not None
    has_resources = bool(state.get("resource_plan"))
    has_notifications = bool(state.get("notifications"))

    if deterministic == "__end__":
        return "__end__", "guarded: workflow already has the required result"

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


async def supervisor_node(state: dict) -> dict:
    iteration = int(state.get("iteration", 0)) + 1
    if iteration > 8:
        return {"next_agent": "__end__", "iteration": iteration, "current_agent": "supervisor"}
    if state.get("error"):
        return {"next_agent": "__end__", "iteration": iteration, "current_agent": "supervisor"}

    user_query = str(state.get("user_query", ""))
    inferred_intent = str(state.get("intent") or _infer_intent(user_query))
    inferred_focus_station = state.get("focus_station_query") or _infer_focus_station_query(user_query)

    # General chat should not be handed back to the workflow planner just because
    # an LLM is available; otherwise simple greetings can drift into analysis.
    if inferred_intent == "general_chat" and not _is_water_domain_query(user_query):
        return {
            "next_agent": "conversation_assistant",
            "iteration": iteration,
            "current_agent": "supervisor",
            "intent": inferred_intent,
            "focus_station_query": inferred_focus_station,
            "supervisor_reasoning": "general chat hard route",
        }

    llm = get_llm()
    deterministic = _deterministic_route(state)
    if deterministic == "__end__":
        return {
            "next_agent": "__end__",
            "iteration": iteration,
            "current_agent": "supervisor",
            "intent": inferred_intent,
            "focus_station_query": inferred_focus_station,
            "supervisor_reasoning": "deterministic complete",
        }

    # When LLM is unavailable, fall back to deterministic routing immediately.
    if not llm.is_enabled:
        return {
            "next_agent": deterministic or "__end__",
            "iteration": iteration,
            "current_agent": "supervisor",
            "intent": inferred_intent,
            "focus_station_query": inferred_focus_station,
            "supervisor_reasoning": "deterministic (no llm)",
        }

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
        "guardrails": [
            "防汛业务问题必须先有 data_analyst 提供监测数据 grounding，除非是闲聊或知识库问答。",
            "预案、资源、通知必须建立在 risk_assessor 的风险评估之后。",
            "资源调度和通知必须建立在 plan_generator 的预案之后。",
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

    return {
        "next_agent": next_agent,
        "iteration": iteration,
        "current_agent": "supervisor",
        "intent": intent,
        "focus_station_query": focus_station_query,
        "supervisor_reasoning": reasoning,
    }
