"""Supervisor 智能体 — 任务路由与协调中心

负责理解用户意图，将任务分配给合适的子智能体，
并在工作流结束时汇总最终响应。
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field

from app.services.llm import get_llm
from app.state import AgentName, FloodResponseState
from app.utils.json_parser import extract_json

# ──────────────────────────────────────────────
# 意图分类关键词
# ──────────────────────────────────────────────

# 完整应急响应流水线关键词
_FULL_RESPONSE_KEYWORDS = [
    "应急", "预案", "响应", "调度", "通知", "完整", "方案", "救援",
    "部署", "全面", "综合", "紧急", "防洪", "抢险",
]
# 仅执行监控
_MONITOR_KEYWORDS = ["进度", "执行", "完成情况", "监控", "跟踪"]
# 仅数据查询
_DATA_ONLY_KEYWORDS = ["水位", "雨量", "流量", "数据", "查询", "当前", "实时", "监测"]
# 仅风险评估
_RISK_ONLY_KEYWORDS = ["风险", "威胁", "是否", "评估", "等级"]


def _classify_intent(user_query: str) -> str:
    """
    根据用户查询关键词分类意图。

    Returns:
        "full_response" | "monitor_only" | "data_only" | "risk_only" | "unknown"
    """
    q = user_query.lower()
    # 优先匹配完整响应（关键词最多）
    if any(kw in q for kw in _FULL_RESPONSE_KEYWORDS):
        return "full_response"
    if any(kw in q for kw in _MONITOR_KEYWORDS):
        return "monitor_only"
    if any(kw in q for kw in _RISK_ONLY_KEYWORDS):
        return "risk_only"
    if any(kw in q for kw in _DATA_ONLY_KEYWORDS):
        return "data_only"
    return "unknown"


def _deterministic_route(state: FloodResponseState, intent: str) -> str | None:
    """
    确定性路由规则引擎。

    根据已完成步骤（state 字段存在性）直接决定下一步，
    无需调用 LLM，消除不稳定的 LLM 路由死循环。

    Returns:
        下一个 agent 名称，或 None（表示需要 LLM 兜底决策）。
    """
    # 最大迭代防护
    if state.get("iteration", 0) >= 8:
        return "__end__"
    if state.get("error"):
        return "__end__"

    has_data = bool(state.get("data_summary"))
    has_risk = bool(state.get("risk_assessment"))
    has_plan = bool(state.get("emergency_plan") and state["emergency_plan"].plan_id)
    has_resource = bool(state.get("resource_plan"))
    has_notifications = bool(state.get("notifications"))

    # ── 执行监控意图 ──
    if intent == "monitor_only":
        return "execution_monitor"

    # ── 仅数据查询意图 ──
    if intent == "data_only":
        if not has_data:
            return "data_analyst"
        return "__end__"

    # ── 仅风险评估意图 ──
    if intent == "risk_only":
        if not has_data:
            return "data_analyst"
        if not has_risk:
            return "risk_assessor"
        return "__end__"

    # ── 完整流水线（full_response 或 unknown 都走完整流水线）──
    if not has_data:
        return "data_analyst"
    if not has_risk:
        return "risk_assessor"
    if not has_plan:
        return "plan_generator"

    # 资源调度与通知：优先 parallel_dispatch，缺任一时单独补全
    if not has_resource and not has_notifications:
        return "parallel_dispatch"
    if not has_resource:
        return "resource_dispatcher"
    if not has_notifications:
        return "notification"

    # 所有步骤完成
    return "__end__"


SUPERVISOR_SYSTEM_PROMPT = """你是防洪应急预案多智能体系统的 **主管(Supervisor)**。

你的职责：
1. 理解用户的请求意图
2. 决定下一步应该由哪个子智能体来处理
3. 当所有必要步骤完成后，汇总最终响应

可用的子智能体：
- **data_analyst**: 数据分析智能体 — 采集和分析水位、雨量、传感器数据
- **risk_assessor**: 风险评估智能体 — 基于数据评估洪水风险等级
- **plan_generator**: 预案生成智能体 — 生成应急响应预案
- **resource_dispatcher**: 资源调度智能体 — 制定人员物资调度方案
- **notification**: 通知智能体 — 制定预警通知方案
- **execution_monitor**: 执行监控智能体 — 监控预案执行进展
- **parallel_dispatch**: 并行调度 — 同时执行资源调度和通知方案（当两者都需要时优先选择）

路由规则：
- 用户询问当前水情/数据 → data_analyst
- 用户询问风险等级/是否有洪水威胁 → 先 data_analyst，再 risk_assessor
- 用户要求生成应急预案 → data_analyst → risk_assessor → plan_generator
- 用户要求完整的应急响应方案 → data_analyst → risk_assessor → plan_generator → parallel_dispatch
- 用户询问当前执行进度 → execution_monitor
- 所有子智能体工作完成 → 输出 "__end__" 结束

请根据当前进展和用户意图，选择下一个最合适的智能体。
"""


class SupervisorDecision(BaseModel):
    """Supervisor 路由决策"""

    next_agent: Literal[
        "data_analyst",
        "risk_assessor",
        "plan_generator",
        "resource_dispatcher",
        "notification",
        "execution_monitor",
        "parallel_dispatch",
        "__end__",
    ] = Field(description="下一个要执行的智能体名称，或 __end__ 表示结束")
    reasoning: str = Field(default="", description="路由决策的理由说明")


def _extract_response_text(response: object) -> str:
    """兼容不同模型返回格式，尽量提取纯文本内容。"""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
                continue
            text = getattr(item, "text", None) or getattr(item, "content", None)
            if text:
                parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content).strip()


async def supervisor_node(state: FloodResponseState) -> dict:
    """Supervisor 节点：确定性路由引擎优先，LLM 兜底"""
    iteration = state.get("iteration", 0)
    user_query = state.get("user_query", "")

    # ── 第一步：确定性路由 ──
    intent = _classify_intent(user_query)
    deterministic_result = _deterministic_route(state, intent)

    if deterministic_result is not None:
        logger.info(
            f"Supervisor 确定性路由 -> {deterministic_result} "
            f"(intent={intent}, iteration={iteration + 1})",
        )
        return {
            "current_agent": AgentName.SUPERVISOR,
            "next_agent": deterministic_result,
            "iteration": iteration + 1,
            "messages": [{"role": "supervisor", "content": f"[确定性路由] -> {deterministic_result}"}],
        }

    # ── 第二步：LLM 兜底（仅当规则无法确定时）──
    logger.debug(f"Supervisor 规则无法确定路由，调用 LLM 兜底 (intent={intent})")
    llm = get_llm()

    messages = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)]

    # 注入最近 3 轮会话历史（如果存在）
    chat_history = state.get("chat_history", [])
    if chat_history:
        recent = chat_history[-3:]
        history_text = "\n".join(
            f"[{turn.get('role', 'user')}]: {turn.get('content', '')[:200]}"
            for turn in recent
        )
        messages.append(HumanMessage(content=f"最近对话历史:\n{history_text}"))

    if user_query:
        messages.append(HumanMessage(content=f"用户请求: {user_query}"))

    # 添加当前进展上下文
    context_parts = []
    if state.get("data_summary"):
        context_parts.append(f"[数据分析已完成] {state['data_summary'][:300]}")
    if state.get("risk_assessment"):
        ra = state["risk_assessment"]
        context_parts.append(f"[风险评估已完成] 等级={ra.risk_level.value}, 分数={ra.risk_score}")
    if state.get("emergency_plan") and state["emergency_plan"].plan_id:
        ep = state["emergency_plan"]
        context_parts.append(f"[预案已生成] {ep.plan_name}, 包含{len(ep.actions)}项措施")
    if state.get("resource_plan"):
        context_parts.append(f"[资源调度已完成] 共{len(state['resource_plan'])}项调度")
    if state.get("notifications"):
        context_parts.append(f"[通知方案已完成] 共{len(state['notifications'])}条通知")
    if context_parts:
        messages.append(HumanMessage(content="当前进展:\n" + "\n".join(context_parts)))

    next_agent_raw = "__end__"
    reasoning = ""
    try:
        json_response = await llm.ainvoke(
            messages
            + [
                SystemMessage(
                    content="""请只返回一个 JSON 对象，不要附带额外说明：
{
  "next_agent": "data_analyst|risk_assessor|plan_generator|resource_dispatcher|notification|execution_monitor|parallel_dispatch|__end__",
  "reasoning": "简短说明"
}""",
                )
            ],
        )
        content = _extract_response_text(json_response)
        parsed = extract_json(content)
        if not isinstance(parsed, dict):
            raise ValueError(f"无法从响应中提取 JSON: {content[:200]}")

        decision = SupervisorDecision.model_validate(
            {
                "next_agent": parsed.get("next_agent", "__end__"),
                "reasoning": parsed.get("reasoning", ""),
            }
        )
        next_agent_raw = decision.next_agent
        reasoning = decision.reasoning
        logger.debug(f"Supervisor LLM路由: {next_agent_raw}, 理由: {reasoning[:100]}")
    except Exception as e:
        logger.warning(f"JSON 路由失败，回退到文本解析: {e}")
        fallback_messages = messages + [
            SystemMessage(content="""请根据上述上下文，只回复以下之一（不要任何解释）：
- data_analyst
- risk_assessor
- plan_generator
- resource_dispatcher
- notification
- execution_monitor
- parallel_dispatch
- __end__""")
        ]
        response = await llm.ainvoke(fallback_messages)
        content = _extract_response_text(response).lower()
        valid_agents_list = ["data_analyst", "risk_assessor", "plan_generator",
            "resource_dispatcher", "notification", "execution_monitor",
            "parallel_dispatch", "__end__",
        ]
        for agent in valid_agents_list:
            if agent in content:
                next_agent_raw = agent
                break
        else:
            next_agent_raw = "__end__"
        logger.debug(f"文本回退解析结果: {next_agent_raw}")

    # 验证路由结果有效性
    valid_agents = {a.value for a in AgentName} | {"__end__"}
    if next_agent_raw not in valid_agents:
        logger.warning(f"Supervisor 返回无效路由: {next_agent_raw}，默认结束")
        next_agent_raw = "__end__"

    logger.info(f"Supervisor LLM兜底路由 -> {next_agent_raw} (iteration={iteration + 1})")

    return {
        "current_agent": AgentName.SUPERVISOR,
        "next_agent": next_agent_raw,
        "iteration": iteration + 1,
        "messages": [{"role": "supervisor", "content": f"[LLM路由] -> {next_agent_raw}"}],
    }
