"""Final aggregation node."""

from __future__ import annotations

import json

from app.services.llm import get_llm
from app.state import to_plain_data


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
                f"从综合研判看，当前整体风险等级为 **{_risk_level_text(assessment)}**，评分 {assessment.risk_score:.1f}。"
            )
            if assessment.key_risks:
                sections.append("最需要盯住的是：" + "；".join(assessment.key_risks[:4]) + "。")
    elif intent == "alarm_overview":
        if summary:
            sections.append(summary)
        if assessment:
            sections.append(
                f"从风险联动角度看，当前整体风险等级为 **{_risk_level_text(assessment)}**，评分 {assessment.risk_score:.1f}。"
            )
            if assessment.key_risks:
                sections.append("和告警态势最相关的风险信号有：" + "；".join(assessment.key_risks[:4]) + "。")
    elif intent == "risk_assessment":
        if assessment:
            sections.append(
                f"我的结论是：当前整体风险等级为 **{_risk_level_text(assessment)}**，综合评分 {assessment.risk_score:.1f}。"
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
                f"当前风险等级为 **{_risk_level_text(assessment)}**，评分 {assessment.risk_score:.1f}，可以作为预案执行优先级依据。"
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
    if error:
        sections.append(f"本次处理还捕获到一个异常：{error}")
    return "\n\n".join(sections).strip() or "综合研判已完成。"


async def final_response_node(state: dict) -> dict:
    focus_station = state.get("focus_station")
    intent = state.get("intent", "overview")
    final_text = _build_fallback_response(state)
    llm = get_llm()
    if llm.is_enabled:
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
                    "error": state.get("error"),
                    "fallback_report": final_text,
                }, ensure_ascii=False, indent=2),
                system_prompt=(
                    "你是防汛 AI 助手的最终回答智能体。"
                    f"本次回答风格应为：{response_style}。"
                    "请优先直接回应用户问题，而不是机械罗列字段。"
                    "如果用户问的是某个站点，就围绕该站点回答，不要退回到全局总览。"
                    "如果 should_include_summary 为 false，就不要先铺垫整体总览，只保留与当前问题直接相关的分析与结论。"
                    "只有在确实需要时再使用分节标题；不要把内部工作流痕迹暴露给用户。"
                    "若存在异常信息，需要在结尾单独提醒。"
                    "输出 Markdown。"
                ),
                temperature=0.2,
            )
            content = getattr(response, "content", "").strip()
            if content:
                final_text = content
        except Exception:
            pass

    return {
        "final_response": final_text,
        "current_agent": "final_response",
        "messages": [{"role": "final_response", "content": final_text}],
    }
