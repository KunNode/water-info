"""Final aggregation node."""

from __future__ import annotations

import asyncio
import json
import logging

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agents.output_validator import validate_final_response
from app.agents._prompt import session_context_payload
from app.rag.service import format_evidence_markdown
from app.services.llm import get_llm
from app.state import get_stream_queue, to_plain_data
from app.tools.trace import make_trace
from app.utils.llm_output_harness import StructuredOutputHarness

logger = logging.getLogger(__name__)

_EVIDENCE_HEADING = "## 证据片段"
_PLAN_RESPONSE_INTENTS = {"plan_generation"}


class FinalResponsePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    conclusion: str
    key_points: list[str] = Field(default_factory=list, max_length=6)
    recommendations: list[str] = Field(default_factory=list, max_length=6)
    warnings: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("conclusion")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


_FINAL_OUTPUT_HARNESS = StructuredOutputHarness(
    FinalResponsePayload,
    name="FinalResponsePayload",
)


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


def _clean_items(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text:
            cleaned.append(text)
    return cleaned


def _render_final_payload(payload: FinalResponsePayload) -> str:
    sections = [f"## 结论\n{payload.conclusion}"]
    key_points = _clean_items(payload.key_points)
    recommendations = _clean_items(payload.recommendations)
    warnings = _clean_items(payload.warnings)
    if key_points:
        sections.append("## 要点\n" + "\n".join(f"- {item}" for item in key_points))
    if recommendations:
        sections.append("## 建议\n" + "\n".join(f"- {item}" for item in recommendations))
    if warnings:
        sections.append("## 提醒\n" + "\n".join(f"- {item}" for item in warnings))
    return "\n\n".join(sections).strip()


def _field(value, name: str, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _format_minutes(value) -> str:
    if value is None:
        return "未限定"
    return f"{value} 分钟"


def _render_action_line(index: int, action) -> str:
    priority = _field(action, "priority", 3)
    description = _field(action, "description", "") or "按预案要求落实处置"
    dept = _field(action, "responsible_dept", "") or "待指派"
    deadline = _format_minutes(_field(action, "deadline_minutes"))
    return f"{index}. [优先级 {priority}] {description}（责任：{dept}；时限：{deadline}）"


def _render_resource_line(index: int, resource) -> str:
    name = _field(resource, "resource_name", "") or "应急资源"
    resource_type = _field(resource, "resource_type", "") or "未分类"
    quantity = _field(resource, "quantity", "")
    source = _field(resource, "source_location", "") or "待确认"
    target = _field(resource, "target_location", "") or "重点防汛区域"
    eta = _format_minutes(_field(resource, "eta_minutes"))
    quantity_text = f" x{quantity}" if quantity not in ("", None) else ""
    return f"{index}. {name}{quantity_text}（类型：{resource_type}；来源：{source}；目标：{target}；到位：{eta}）"


def _render_notification_line(index: int, notification) -> str:
    target = _field(notification, "target", "") or "待确认对象"
    channel = _field(notification, "channel", "") or "默认渠道"
    content = _field(notification, "content", "") or "请按预案要求落实值守和处置。"
    status = _field(notification, "status", "") or "pending"
    return f"{index}. {target}（渠道：{channel}；状态：{status}）：{content}"


def _build_plan_response(state: dict) -> str:
    plan = state.get("emergency_plan")
    assessment = state.get("risk_assessment")
    evidence = state.get("evidence") or []
    error = state.get("error")
    if not plan:
        return _build_fallback_response({**state, "intent": "overview"})

    plan_name = _field(plan, "plan_name", "防汛应急预案")
    plan_risk_level = _field(plan, "risk_level", "") or "none"
    risk_level = _risk_level_text(assessment) if assessment else (getattr(plan_risk_level, "value", plan_risk_level) or "none")
    trigger = _field(plan, "trigger_conditions", "") or "综合风险达到响应阈值"
    summary = _field(plan, "summary", "") or "根据当前水情和风险评估生成的应急响应草案。"
    actions = list(_field(plan, "actions", []) or [])
    resources = list(_field(plan, "resources", []) or [])
    notifications = list(_field(plan, "notifications", []) or [])

    sections = [
        (
            "## 预案概览\n"
            f"- 预案名称：{plan_name}\n"
            f"- 风险等级：{risk_level}\n"
            f"- 触发条件：{trigger}\n"
            f"- 预案摘要：{summary}"
        ),
        "## 处置措施\n" + (
            "\n".join(_render_action_line(index, action) for index, action in enumerate(actions[:12], start=1))
            if actions
            else "- 暂无结构化处置措施，按值班制度先行巡查和会商。"
        ),
        "## 资源配置\n" + (
            "\n".join(_render_resource_line(index, resource) for index, resource in enumerate(resources[:12], start=1))
            if resources
            else "- 暂无结构化资源配置，先由应急仓库和属地队伍待命。"
        ),
        "## 通知安排\n" + (
            "\n".join(
                _render_notification_line(index, notification)
                for index, notification in enumerate(notifications[:20], start=1)
            )
            if notifications
            else "- 暂无结构化通知安排，由防汛值班人员按预案摘要同步相关责任单位。"
        ),
    ]

    reminders: list[str] = []
    if assessment and getattr(assessment, "key_risks", None):
        reminders.append("重点风险：" + "；".join(assessment.key_risks[:4]) + "。")
    reminders.append("执行过程中需持续回看水位、雨量、告警和现场反馈，必要时升级响应。")
    if error:
        reminders.append(f"本次处理还捕获到一个异常：{error}")
    sections.append("## 执行提醒\n" + "\n".join(f"- {item}" for item in reminders))
    return _append_evidence_if_missing("\n\n".join(sections).strip(), evidence)


def _build_fallback_payload(state: dict) -> FinalResponsePayload:
    focus_station = state.get("focus_station")
    intent = state.get("intent", "overview")
    summary = str(state.get("data_summary") or "").strip()
    assessment = state.get("risk_assessment")
    plan = state.get("emergency_plan")
    error = state.get("error")
    key_points: list[str] = []
    recommendations: list[str] = []
    warnings: list[str] = []

    if intent == "general_chat":
        return FinalResponsePayload(
            conclusion=summary or "我在这儿，你可以直接问我站点状态、风险研判或预案问题。",
        )

    if focus_station:
        station_name = focus_station.get("name") or focus_station.get("code") or "该站点"
        if summary:
            key_points.append(summary)
        if assessment:
            key_points.append(
                f"我的当前判断是：{station_name} 风险等级为 **{_risk_level_text(assessment)}**，"
                f"综合评分 {assessment.risk_score:.1f}。"
            )
            if assessment.key_risks:
                key_points.append("需要重点关注：" + "；".join(assessment.key_risks[:3]) + "。")
        if error:
            warnings.append(error)
        recommendations.append("可以继续围绕该站点判断后续处置优先级。")
        return FinalResponsePayload(
            conclusion=f"你问的是 {station_name}。",
            key_points=key_points,
            recommendations=recommendations,
            warnings=warnings,
        )

    conclusion = "综合研判已完成。"
    if intent == "overview":
        if summary:
            conclusion = summary
        if assessment:
            key_points.append(
                f"从综合研判看，当前整体风险等级为 **{_risk_level_text(assessment)}**，"
                f"评分 {assessment.risk_score:.1f}。"
            )
            if assessment.key_risks:
                key_points.append("最需要盯住的是：" + "；".join(assessment.key_risks[:4]) + "。")
    elif intent == "alarm_overview":
        if summary:
            conclusion = summary
        if assessment:
            key_points.append(
                f"从风险联动角度看，当前整体风险等级为 **{_risk_level_text(assessment)}**，"
                f"评分 {assessment.risk_score:.1f}。"
            )
            if assessment.key_risks:
                key_points.append("和告警态势最相关的风险信号有：" + "；".join(assessment.key_risks[:4]) + "。")
    elif intent == "risk_assessment":
        if assessment:
            conclusion = (
                f"我的结论是：当前整体风险等级为 **{_risk_level_text(assessment)}**，"
                f"综合评分 {assessment.risk_score:.1f}。"
            )
            if assessment.key_risks:
                key_points.append("主要依据包括：" + "；".join(assessment.key_risks[:4]) + "。")
        elif summary:
            conclusion = summary
    elif intent in {"plan_generation", "resource_dispatch", "notification"}:
        if plan:
            conclusion = f"已基于当前态势形成预案《{plan.plan_name}》。"
            if plan.summary:
                key_points.append(plan.summary)
            actions = getattr(plan, "actions", None) or []
            recommendations.extend(action.description for action in actions[:4])
        if assessment:
            key_points.append(
                f"当前风险等级为 **{_risk_level_text(assessment)}**，评分 {assessment.risk_score:.1f}，"
                "可以作为预案执行优先级依据。"
            )
        elif _should_include_summary(state) and summary:
            key_points.append(summary)
    else:
        if _should_include_summary(state) and summary:
            conclusion = summary
        if assessment:
            key_points.append(
                f"综合风险等级为 **{_risk_level_text(assessment)}**，评分 {assessment.risk_score:.1f}。"
            )
            if assessment.key_risks:
                key_points.append("当前重点风险包括：" + "；".join(assessment.key_risks[:4]) + "。")

    if error:
        warnings.append(error)
    return FinalResponsePayload(
        conclusion=conclusion,
        key_points=key_points,
        recommendations=recommendations,
        warnings=warnings,
    )


def _build_fallback_response(state: dict) -> str:
    if state.get("intent") in _PLAN_RESPONSE_INTENTS and state.get("emergency_plan"):
        return _build_plan_response(state)
    text = _render_final_payload(_build_fallback_payload(state))
    return _append_evidence_if_missing(text, state.get("evidence") or [])


async def final_response_node(state: dict) -> dict:
    traces: list[dict] = [
        make_trace(phase="final_response", status="started", title="正在生成最终回答"),
    ]

    focus_station = state.get("focus_station")
    intent = state.get("intent", "overview")
    draft = (state.get("final_response_draft") or "").strip()
    evidence = state.get("evidence") or []
    answer_policy = state.get("answer_policy") or {}
    is_plan_response = intent in _PLAN_RESPONSE_INTENTS and state.get("emergency_plan") is not None

    # Analytical intents where risk_assessment must take precedence over RAG draft
    _ANALYTICAL_INTENTS = {"risk_assessment", "station_status", "overview", "alarm_overview"}
    has_risk_assessment = state.get("risk_assessment") is not None

    if is_plan_response:
        final_text = _build_plan_response(state)
    elif draft and not (intent in _ANALYTICAL_INTENTS and has_risk_assessment):
        # Upstream agent (conversation_assistant / knowledge_retriever answer mode) already
        # produced the answer text. Use it as-is, skip the heavy LLM rewrite, but still run
        # validation and unified evidence appending so the heading appears at most once.
        # EXCEPT: when analytical intent has risk_assessment, the draft from RAG preflight
        # may not reflect the computed risk level — fall through to LLM rewrite instead.
        final_text = _append_evidence_if_missing(draft, evidence)
    elif answer_policy.get("data_only") and state.get("data_summary"):
        final_text = str(state.get("data_summary") or "").strip()
    else:
        final_text = _build_fallback_response(state)

    pre_report = validate_final_response(final_text, state)

    llm = get_llm()
    stream_queue = get_stream_queue()
    draft_overridden = draft and intent in _ANALYTICAL_INTENTS and has_risk_assessment
    if llm.is_enabled and (not draft or draft_overridden) and not answer_policy.get("data_only") and not is_plan_response:
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

            llm_prompt = json.dumps({
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
                "memory_context": session_context_payload(state),
                "error": state.get("error"),
                "must_satisfy": must_satisfy,
                "llm_context": {
                    "final_response_generated_by_llm": True,
                    "grounding_sources": ["structured_monitoring_data", "risk_rules", "rag_evidence_if_available"],
                },
                "fallback_report": final_text,
            }, ensure_ascii=False, indent=2)
            # Build system prompt based on streaming mode
            if stream_queue is not None:
                # Streaming mode: output plain text directly
                system_prompt = (
                    "你是防汛 AI 助手的最终回答智能体。"
                    f"本次回答风格应为：{response_style}。"
                    "请直接用自然语言回答用户问题，不要输出 JSON 格式。"
                    "回答应包含：结论、要点、建议、提醒等部分，用 Markdown 格式组织。"
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
                    "证据片段会由系统统一在结尾追加，正文不要再写 ## 证据片段 这一节。"
                    "若存在异常信息，需要在结尾单独提醒。"
                )
            else:
                # Non-streaming mode: output JSON for structured parsing
                system_prompt = (
                    "你是防汛 AI 助手的最终回答智能体。"
                    f"本次回答风格应为：{response_style}。"
                    "你的职责是填充固定回答槽位，而不是自由排版。"
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
                    "不要输出 Markdown 标题；系统会按固定顺序渲染为：结论、要点、建议、提醒。"
                    "证据片段会由系统统一在结尾追加，正文不要再写 ## 证据片段 这一节。"
                    "若存在异常信息，需要在结尾单独提醒。"
                    f"{_FINAL_OUTPUT_HARNESS.schema_instruction()}"
                )

            # Use streaming if queue is available, otherwise fallback to non-streaming
            if stream_queue is not None:
                # Streaming mode: collect tokens and send to queue
                content_parts = []
                async for token in llm.astream(
                    llm_prompt,
                    system_prompt=system_prompt,
                    temperature=0.0,
                    # No JSON format for streaming - output plain text
                ):
                    content_parts.append(token)
                    await stream_queue.put(token)
                content = "".join(content_parts).strip()
                # For streaming, the content is the final text (already formatted)
                final_text = _append_evidence_if_missing(content, evidence)
            else:
                # Non-streaming mode: use JSON format for structured parsing
                response = await llm.ainvoke(
                    llm_prompt,
                    system_prompt=system_prompt,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                content = getattr(response, "content", "").strip()
                harness_result = _FINAL_OUTPUT_HARNESS.parse(content)
                if harness_result.ok and harness_result.payload is not None:
                    final_text = _append_evidence_if_missing(_render_final_payload(harness_result.payload), evidence)
                elif harness_result.issues:
                    logger.warning(
                        "final_response LLM output failed harness validation: %s",
                        "; ".join(harness_result.issues[:5]),
                    )
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
                        "不要新增 ## 证据片段。"
                        "按固定槽位输出 JSON，不要输出 Markdown。"
                        f"{_FINAL_OUTPUT_HARNESS.schema_instruction()}"
                    ),
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                repaired = getattr(repair, "content", "").strip()
                if repaired:
                    repair_result = _FINAL_OUTPUT_HARNESS.parse(repaired)
                    if not repair_result.ok or repair_result.payload is None:
                        raise ValueError("final response repair did not satisfy harness")
                    candidate = _append_evidence_if_missing(_render_final_payload(repair_result.payload), evidence)
                    if validate_final_response(candidate, state).ok:
                        final_text = candidate
            except Exception:
                pass
        if not validate_final_response(final_text, state).ok:
            logger.warning(
                "final_response validation failed, falling back to deterministic text: %s",
                post_report.issues,
            )
            traces.append(make_trace(
                phase="final_response",
                status="failed",
                title="回答校验未通过，使用兜底回答",
                detail="; ".join(post_report.issues[:3]),
            ))
            final_text = _build_fallback_response(state)

    traces.append(make_trace(
        phase="final_response",
        status="completed",
        title="最终回答生成完成",
        detail=f"回答长度 {len(final_text)} 字符",
    ))

    return {
        "final_response": final_text,
        "current_agent": "final_response",
        "messages": [{"role": "final_response", "content": final_text}],
        "execution_traces": traces,
    }
