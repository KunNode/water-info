"""Final aggregation node."""

from __future__ import annotations

import json
import logging

from app.agents.output_validator import validate_final_response
from app.rag.service import format_evidence_markdown
from app.services.llm import get_llm
from app.state import to_plain_data

logger = logging.getLogger(__name__)

_EVIDENCE_HEADING = "## 证据片段"


def _append_evidence_if_missing(text: str, evidence) -> str:
    if not evidence:
        return text
    if _EVIDENCE_HEADING in text:
        return text
    block = format_evidence_markdown(evidence)
    if not block:
        return text
    return f"{text}\n\n{block}".strip()


def _risk_level_text(assessment) -> str:
    if not assessment:
        return "none"
    risk_level = getattr(assessment, "risk_level", None)
    return getattr(risk_level, "value", risk_level) or "none"


def _should_include_summary(state: dict) -> bool:
    intent = state.get("intent", "overview")
    if state.get("focus_station"):
        return True
    if intent == "overview":
        return True
    if not state.get("risk_assessment") and not state.get("emergency_plan"):
        return True
    return False


def _build_fallback_response(state: dict) -> str:
    focus_station = state.get("focus_station")
    intent = state.get("intent", "overview")
    summary = str(state.get("data_summary") or "").strip()
    assessment = state.get("risk_assessment")
    plan = state.get("emergency_plan")
    evidence = state.get("evidence") or []
    error = state.get("error")

    if intent == "general_chat":
        return summary or "我在这儿，你可以直接问我站点状态、风险研判或预案问题。"

    if focus_station:
        station_name = focus_station.get("name") or focus_station.get("code") or "该站点"
        parts = [f"你问的是 {station_name}。"]
        if summary:
            parts.append(summary)
        if assessment:
            parts.append(
                f"我的当前判断是：{station_name} 风险等级为 **{_risk_level_text(assessment)}**，"
                f"综合评分 {assessment.risk_score:.1f}。"
            )
            if assessment.key_risks:
                parts.append("需要重点关注：" + "；".join(assessment.key_risks[:3]) + "。")
        if error:
            parts.append(f"另外，这次分析里还有一个异常需要注意：{error}")
        parts.append("如果你愿意，我可以继续帮你判断这个站点接下来该怎么处置。")
        return "\n\n".join(parts)

    sections: list[str] = []
    if intent == "overview":
        if summary:
            sections.append(summary)
        if assessment:
            sections.append(
                f"从综合研判看，当前整体风险等级为 **{_risk_level_text(assessment)}**，"
                f"评分 {assessment.risk_score:.1f}。"
            )
            if assessment.key_risks:
                sections.append("最需要盯住的是：" + "；".join(assessment.key_risks[:4]) + "。")
    elif intent == "alarm_overview":
        if summary:
            sections.append(summary)
        if assessment:
            sections.append(
                f"从风险联动角度看，当前整体风险等级为 **{_risk_level_text(assessment)}**，"
                f"评分 {assessment.risk_score:.1f}。"
            )
            if assessment.key_risks:
                sections.append("和告警态势最相关的风险信号有：" + "；".join(assessment.key_risks[:4]) + "。")
    elif intent == "risk_assessment":
        if assessment:
            sections.append(
                f"我的结论是：当前整体风险等级为 **{_risk_level_text(assessment)}**，"
                f"综合评分 {assessment.risk_score:.1f}。"
            )
            if assessment.key_risks:
                sections.append("主要依据包括：" + "；".join(assessment.key_risks[:4]) + "。")
        elif summary:
            sections.append(summary)
    elif intent in {"plan_generation", "resource_dispatch", "notification"}:
        if plan:
            sections.append(f"已基于当前态势形成预案《{plan.plan_name}》。")
            if plan.summary:
                sections.append(plan.summary)
        if assessment:
            sections.append(
                f"当前风险等级为 **{_risk_level_text(assessment)}**，评分 {assessment.risk_score:.1f}，"
                "可以作为预案执行优先级依据。"
            )
        elif _should_include_summary(state) and summary:
            sections.append(summary)
    else:
        if _should_include_summary(state) and summary:
            sections.append(summary)
        if assessment:
            sections.append(
                f"综合风险等级为 **{_risk_level_text(assessment)}**，评分 {assessment.risk_score:.1f}。"
            )
            if assessment.key_risks:
                sections.append("当前重点风险包括：" + "；".join(assessment.key_risks[:4]) + "。")

    if plan and intent in {"plan_generation", "resource_dispatch", "notification"}:
        sections.append(f"已形成预案《{plan.plan_name}》，可继续展开措施、资源和通知安排。")
    merged = "\n\n".join(sections).strip()
    if evidence and _EVIDENCE_HEADING not in merged:
        block = format_evidence_markdown(evidence)
        if block:
            merged = f"{merged}\n\n{block}".strip() if merged else block
    if error:
        merged = f"{merged}\n\n本次处理还捕获到一个异常：{error}".strip()
    return merged or "综合研判已完成。"


async def final_response_node(state: dict) -> dict:
    focus_station = state.get("focus_station")
    intent = state.get("intent", "overview")
    draft = (state.get("final_response_draft") or "").strip()
    evidence = state.get("evidence") or []

    if draft:
        # Upstream agent (conversation_assistant / knowledge_retriever answer mode) already
        # produced the answer text. Use it as-is, skip the heavy LLM rewrite, but still run
        # validation and unified evidence appending so the heading appears at most once.
        final_text = _append_evidence_if_missing(draft, evidence)
    else:
        final_text = _build_fallback_response(state)

    pre_report = validate_final_response(final_text, state)

    llm = get_llm()
    if llm.is_enabled and not draft:
        try:
            response_style = "自然、友好的助手对话"
            if intent in {"plan_generation", "resource_dispatch", "notification"}:
                response_style = "面向指挥人员的执行建议报告"
            elif intent in {"station_status", "risk_assessment"} or focus_station:
                response_style = "先给结论、再给依据的站点答复"
            elif intent == "alarm_overview":
                response_style = "清楚说明告警数量、分布和重点告警的态势简报"
            elif intent == "overview":
                response_style = "完整但不冗长的态势研判简报"

            must_satisfy = list(pre_report.issues)
            consistency_clause = (
                "请确保叙述与结构化字段一致：风险等级、预案名、措施/资源/通知的数量都要对得上。"
            )
            if must_satisfy:
                consistency_clause += f"特别注意修正以下问题：{'；'.join(must_satisfy)}。"

            response = await llm.ainvoke(
                json.dumps({
                    "user_query": state.get("user_query", ""),
                    "intent": intent,
                    "focus_station": to_plain_data(focus_station),
                    "data_summary": state.get("data_summary", ""),
                    "should_include_summary": _should_include_summary(state),
                    "risk_assessment": to_plain_data(state.get("risk_assessment")),
                    "emergency_plan": to_plain_data(state.get("emergency_plan")),
                    "resource_plan": to_plain_data(state.get("resource_plan", [])),
                    "notifications": to_plain_data(state.get("notifications", [])),
                    "evidence": to_plain_data(evidence),
                    "memory_context": to_plain_data(state.get("memory_context", {})),
                    "error": state.get("error"),
                    "must_satisfy": must_satisfy,
                    "llm_context": {
                        "final_response_generated_by_llm": True,
                        "grounding_sources": ["structured_monitoring_data", "risk_rules", "rag_evidence_if_available"],
                    },
                    "fallback_report": final_text,
                }, ensure_ascii=False, indent=2),
                system_prompt=(
                    "你是防汛 AI 助手的最终回答智能体。"
                    f"本次回答风格应为：{response_style}。"
                    "请优先直接回应用户问题，而不是机械罗列字段。"
                    "如果用户问的是某个站点，就围绕该站点回答，不要退回到全局总览。"
                    "如果 should_include_summary 为 false，就不要先铺垫整体总览，只保留与当前问题直接相关的分析与结论。"
                    "若 evidence 非空，请优先使用 evidence 中的内容，并保留 [1][2] 这类引用。"
                    "memory_context.recent_session_messages 可用于回答同一会话内的刚才/上一轮/代词指代问题。"
                    "memory_context.long_term_memories 可用于用户长期偏好；不要向用户暴露内部记忆机制。"
                    "若 evidence 为空，不要编造外部制度来源。"
                    f"{consistency_clause}"
                    "如果用户询问是否使用模型研判，请说明当前回答由大模型结合结构化监测数据、规则基线"
                    "和可用 RAG 证据生成；不要声称未使用模型。"
                    "只有在确实需要时再使用分节标题；不要把内部工作流痕迹暴露给用户。"
                    "证据片段会由系统统一在结尾追加，正文不要再写 ## 证据片段 这一节。"
                    "若存在异常信息，需要在结尾单独提醒。"
                    "输出 Markdown。"
                ),
                temperature=0.2,
            )
            content = getattr(response, "content", "").strip()
            if content:
                final_text = _append_evidence_if_missing(content, evidence)
        except Exception:
            pass

    post_report = validate_final_response(final_text, state)
    if not post_report.ok:
        if llm.is_enabled:
            try:
                repair = await llm.ainvoke(
                    json.dumps({
                        "current_text": final_text,
                        "issues": post_report.issues,
                        "risk_assessment": to_plain_data(state.get("risk_assessment")),
                        "emergency_plan": to_plain_data(state.get("emergency_plan")),
                        "resource_plan": to_plain_data(state.get("resource_plan", [])),
                        "notifications": to_plain_data(state.get("notifications", [])),
                    }, ensure_ascii=False, indent=2),
                    system_prompt=(
                        "请仅修正以下叙述中与结构化字段不一致的部分："
                        "风险等级、预案名以及措施/资源/通知的数量。"
                        "保留原有 Markdown 风格和 [1][2] 引用，不要新增 ## 证据片段。"
                        "输出修正后的完整文本。"
                    ),
                    temperature=0.0,
                )
                repaired = getattr(repair, "content", "").strip()
                if repaired:
                    candidate = _append_evidence_if_missing(repaired, evidence)
                    if validate_final_response(candidate, state).ok:
                        final_text = candidate
            except Exception:
                pass
        if not validate_final_response(final_text, state).ok:
            logger.warning(
                "final_response validation failed, falling back to deterministic text: %s",
                post_report.issues,
            )
            final_text = _build_fallback_response(state)

    return {
        "final_response": final_text,
        "current_agent": "final_response",
        "messages": [{"role": "final_response", "content": final_text}],
    }
