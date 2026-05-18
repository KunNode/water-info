"""Declarative routing rules: dependency tables and intent classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# ---------------------------------------------------------------------------
# Agent dependency & completion tables (replace _guard_model_route if-chains)
# ---------------------------------------------------------------------------

AGENT_DEPENDENCIES: dict[str, list[str]] = {
    "data_analyst": [],
    "risk_assessor": ["data_summary"],
    "plan_generator": ["risk_assessment"],
    "resource_dispatcher": ["emergency_plan"],
    "notification": ["emergency_plan"],
    "plan_reviewer": ["emergency_plan"],
    "safety_checker": ["emergency_plan"],
    "parallel_dispatch": ["risk_assessment", "emergency_plan"],
    "conversation_assistant": [],
    "knowledge_retriever": [],
    "execution_monitor": [],
}

PRODUCER_MAP: dict[str, str] = {
    "data_summary": "data_analyst",
    "risk_assessment": "risk_assessor",
    "emergency_plan": "plan_generator",
    "resource_plan": "resource_dispatcher",
    "notifications": "notification",
}

COMPLETION_FIELD: dict[str, str] = {
    "data_analyst": "data_summary",
    "risk_assessor": "risk_assessment",
    "plan_generator": "emergency_plan",
    "resource_dispatcher": "resource_plan",
    "notification": "notifications",
    "plan_reviewer": "compliance_result",
    "safety_checker": "safety_check_result",
    "execution_monitor": "execution_progress",
}


def _find_producer(field: str) -> str | None:
    return PRODUCER_MAP.get(field)


def enforce_dependencies(
    next_agent: str,
    state: dict,
    fallback: str | None = None,
) -> tuple[str, str | None]:
    """Enforce workflow preconditions using declarative dependency table.

    Returns (resolved_agent, guard_reason).
    """
    if next_agent in {"__end__", "conversation_assistant", "knowledge_retriever", "execution_monitor"}:
        return next_agent, None

    if next_agent == "__end__":
        if fallback and fallback != "__end__":
            return fallback, "guarded: workflow still has a required next step"
        return next_agent, None

    if not state.get("data_summary"):
        return fallback or "data_analyst", "guarded: data grounding is required first"

    required = AGENT_DEPENDENCIES.get(next_agent, [])
    for field in required:
        if not state.get(field):
            producer = _find_producer(field)
            return producer or fallback or "__end__", f"guarded: missing {field}"

    completion = COMPLETION_FIELD.get(next_agent)
    if completion and state.get(completion):
        return fallback or "__end__", f"guarded: {next_agent} already complete"

    return next_agent, None


# ---------------------------------------------------------------------------
# Intent classification rules (replace _infer_intent if/elif chain)
# ---------------------------------------------------------------------------

_EXECUTION_KEYWORDS = ["执行", "进度", "完成了吗", "落实", "落地", "推进到哪", "执行情况"]
_PLAN_KEYWORDS = ["预案", "方案", "怎么处置", "怎么应对", "响应", "处置方案", "行动建议"]
_RESOURCE_KEYWORDS = ["资源", "物资", "调度", "队伍", "人员", "车辆", "抢险力量", "装备"]
_NOTIFICATION_KEYWORDS = ["通知", "告知", "通报", "谁需要知道", "通知谁", "发送给谁"]
_RISK_KEYWORDS = ["风险", "研判", "评估", "危险吗", "严不严重", "趋势判断"]
_ALARM_KEYWORDS = ["告警", "预警", "报警", "异常", "超限", "告急"]
_OVERVIEW_KEYWORDS = ["总览", "概况", "整体", "总体", "全局", "态势", "情况怎么样", "现在怎么样", "总体情况"]
_STATION_KEYWORDS = ["站", "站点", "水库", "闸", "泵站", "断面"]
_DATA_ONLY_KEYWORDS = ["无需分析", "不用分析", "不要分析", "无须分析", "只要数据", "只看数据", "数据库数据"]
_DATA_LOOKUP_KEYWORDS = ["最新", "数据", "观测", "记录", "明细"]
_KNOWLEDGE_KEYWORDS = [
    "制度", "手册", "规范", "条例", "办法", "流程", "规程",
    "值班要求", "预案模板", "文档", "资料", "文件", "依据",
]
_WATER_DOMAIN_KEYWORDS = [
    *_STATION_KEYWORDS,
    "水情", "水位", "雨量", "洪水", "防汛", "河道", "监测",
    *_ALARM_KEYWORDS, "应急", *_RISK_KEYWORDS, *_PLAN_KEYWORDS,
    *_RESOURCE_KEYWORDS, *_NOTIFICATION_KEYWORDS, *_EXECUTION_KEYWORDS,
]


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def _is_general_chat_query(query: str) -> bool:
    import re

    lowered = query.strip().lower()
    if not lowered:
        return True
    if re.match(r"^(你好|您好|hi|hello|hey|嗨|哈喽|在吗|在不在|你是谁)", lowered):
        return True
    return _contains_any(query, [
        "你能做什么", "怎么用", "帮助", "help",
        "介绍一下你自己", "你是谁", "谢谢", "辛苦了", "再见",
    ])


def _is_data_lookup_query(query: str) -> bool:
    data_only = _contains_any(query, _DATA_ONLY_KEYWORDS)
    data_lookup = data_only or (
        _contains_any(query, _DATA_LOOKUP_KEYWORDS)
        and ("最新" in query or "数据库" in query or "数据" in query)
    )
    return data_lookup


def _has_station_focus(query: str) -> bool:
    import re

    for pattern in [
        r"([A-Za-z0-9\-_]{2,})站点",
        r"站点([A-Za-z0-9一-龥\-_]{2,12})",
        r"([A-Za-z0-9一-龥\-_]{2,12})(?:站|水库|闸|泵站|断面)",
    ]:
        if re.search(pattern, query):
            return True
    return _contains_any(query, _STATION_KEYWORDS)


def _is_alarm_overview_query(query: str, *, has_station_focus: bool) -> bool:
    has_alarm = _contains_any(query, _ALARM_KEYWORDS)
    has_overview = _contains_any(query, _OVERVIEW_KEYWORDS + ["分布", "多少", "有哪些", "哪里", "集中在哪"])
    if has_station_focus:
        return False
    return has_alarm and (has_overview or "告警" in query or "预警" in query)


@dataclass
class IntentRule:
    intent: str
    match_fn: Callable[[str, dict], bool]
    priority: int = 0


def _build_intent_rules() -> list[IntentRule]:
    return [
        IntentRule("general_chat", lambda q, ctx: _is_general_chat_query(q), priority=0),
        IntentRule(
            "data_lookup",
            lambda q, ctx: _is_data_lookup_query(q),
            priority=1,
        ),
        IntentRule("knowledge_qa", lambda q, ctx: _contains_any(q, _KNOWLEDGE_KEYWORDS), priority=2),
        IntentRule("execution_status", lambda q, ctx: _contains_any(q, _EXECUTION_KEYWORDS), priority=3),
        IntentRule("resource_dispatch", lambda q, ctx: _contains_any(q, _RESOURCE_KEYWORDS), priority=4),
        IntentRule("notification", lambda q, ctx: _contains_any(q, _NOTIFICATION_KEYWORDS), priority=5),
        IntentRule("plan_generation", lambda q, ctx: _contains_any(q, _PLAN_KEYWORDS), priority=6),
        IntentRule("risk_assessment", lambda q, ctx: _contains_any(q, _RISK_KEYWORDS), priority=7),
        IntentRule("station_status", lambda q, ctx: _has_station_focus(q), priority=8),
        IntentRule(
            "alarm_overview",
            lambda q, ctx: _is_alarm_overview_query(q, has_station_focus=ctx.get("has_station_focus", False)),
            priority=9,
        ),
        IntentRule(
            "overview",
            lambda q, ctx: _contains_any(q, _OVERVIEW_KEYWORDS) and _contains_any(q, _WATER_DOMAIN_KEYWORDS),
            priority=10,
        ),
        IntentRule("overview", lambda q, ctx: _contains_any(q, _WATER_DOMAIN_KEYWORDS), priority=11),
    ]


_INTENT_RULES = _build_intent_rules()


def infer_intent(query: str, context: dict | None = None) -> str:
    """Classify user intent using prioritised rule list.

    Returns one of the standard intent strings.  Falls back to "general_chat".
    """
    ctx = context or {}
    ctx.setdefault("has_station_focus", _has_station_focus(query))
    for rule in sorted(_INTENT_RULES, key=lambda r: r.priority):
        if rule.match_fn(query, ctx):
            return rule.intent
    return "general_chat"
