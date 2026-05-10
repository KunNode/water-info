"""Plan generator node."""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agents._prompt import session_context_payload
from app.plan import generate_plan_id, get_response_template
from app.services.llm import get_llm
from app.state import EmergencyAction, EmergencyPlan, NotificationRecord, ResourceAllocation, RiskLevel, to_plain_data
from app.utils.llm_output_harness import StructuredOutputHarness

logger = logging.getLogger(__name__)


class PlanActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action_type: str
    description: str
    priority: int = Field(default=3, ge=1, le=5)
    responsible_dept: str = ""
    deadline_minutes: int | None = Field(default=None, ge=0)

    @field_validator("action_type", "description")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class PlanResourcePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    resource_type: str
    resource_name: str
    quantity: int = Field(ge=1)
    source_location: str = ""
    target_location: str = ""
    eta_minutes: int | None = Field(default=None, ge=0)

    @field_validator("resource_type", "resource_name")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class PlanNotificationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target: str
    channel: str = "sms"
    content: str
    status: str = "pending"

    @field_validator("target", "content")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class PlanCitationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    citation_id: str
    document_title: str = ""
    source_uri: str = ""
    content: str = ""

    @field_validator("citation_id")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class EmergencyPlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    plan_name: str
    trigger_conditions: str
    summary: str
    actions: list[PlanActionPayload] = Field(min_length=1)
    resources: list[PlanResourcePayload] = Field(min_length=1)
    notifications: list[PlanNotificationPayload] = Field(default_factory=list)
    citations: list[PlanCitationPayload] = Field(default_factory=list)

    @field_validator("plan_name", "trigger_conditions", "summary")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


_PLAN_OUTPUT_HARNESS = StructuredOutputHarness(
    EmergencyPlanPayload,
    name="EmergencyPlanPayload",
)


def _build_template_plan(plan_id: str, level: str, template: dict, session_id: str) -> EmergencyPlan:
    actions = [
        EmergencyAction(
            action_id=f"{plan_id}-A{i + 1:02d}",
            action_type=item["type"],
            description=item["desc"],
            priority=int(item.get("priority", 3)),
            responsible_dept=template["command_center"],
        )
        for i, item in enumerate(template["actions"])
    ]
    resources = [
        ResourceAllocation(
            resource_type=item["type"],
            resource_name=item["name"],
            quantity=int(item["quantity"]),
            source_location="应急物资仓库",
            target_location="重点防汛区域",
        )
        for item in template["resources"]
    ]
    return EmergencyPlan(
        plan_id=plan_id,
        plan_name=f"{template['response_level']}防汛应急预案",
        risk_level=level,
        trigger_conditions="综合风险达到响应阈值",
        status="draft",
        session_id=session_id,
        summary="根据当前水情和风险评估生成的应急响应草案。",
        actions=actions,
        resources=resources,
    )


def _plan_from_model_payload(
    payload: EmergencyPlanPayload,
    *,
    fallback_plan: EmergencyPlan,
    plan_id: str,
    level: str,
    session_id: str,
    template: dict,
) -> EmergencyPlan:
    actions = [
        EmergencyAction(
            action_id=f"{plan_id}-A{i + 1:02d}",
            action_type=item.action_type,
            description=item.description,
            priority=item.priority,
            responsible_dept=item.responsible_dept or template["command_center"],
            deadline_minutes=item.deadline_minutes,
        )
        for i, item in enumerate(payload.actions[:12])
        if item.action_type and item.description
    ]
    resources = [
        ResourceAllocation(
            resource_type=item.resource_type,
            resource_name=item.resource_name,
            quantity=item.quantity,
            source_location=item.source_location or "应急物资仓库",
            target_location=item.target_location or "重点防汛区域",
            eta_minutes=item.eta_minutes,
        )
        for item in payload.resources[:12]
        if item.resource_type and item.resource_name
    ]
    if not actions or not resources:
        return fallback_plan

    return EmergencyPlan(
        plan_id=plan_id,
        plan_name=payload.plan_name or fallback_plan.plan_name,
        risk_level=level,
        trigger_conditions=payload.trigger_conditions or fallback_plan.trigger_conditions,
        status="draft",
        session_id=session_id,
        summary=payload.summary or fallback_plan.summary,
        actions=actions,
        resources=resources,
        notifications=[
            NotificationRecord(
                target=item.target,
                channel=item.channel,
                content=item.content,
                status=item.status,
            )
            for item in payload.notifications[:20]
            if item.target and item.content
        ],
        citations=[item.model_dump(exclude_none=True) for item in payload.citations],
    )


async def plan_generator_node(state: dict) -> dict:
    assessment = state.get("risk_assessment")
    evidence = list(state.get("evidence_context") or [])
    level = assessment.risk_level.value if assessment else RiskLevel.LOW.value
    level = level if level != RiskLevel.NONE.value else RiskLevel.LOW.value
    template = get_response_template(level)
    plan_id = generate_plan_id()
    plan = _build_template_plan(plan_id, level, template, str(state.get("session_id", "")))

    llm = get_llm()
    message = f"已生成预案 {plan.plan_name}"
    if llm.is_enabled:
        try:
            response = await llm.ainvoke(
                json.dumps({
                    "user_query": state.get("user_query", ""),
                    "risk_assessment": to_plain_data(assessment),
                    "data_summary": state.get("data_summary", ""),
                    "evidence": to_plain_data(evidence),
                    "memory_context": session_context_payload(state),
                    "template_reference": template,
                    "fallback_plan": to_plain_data(plan),
                }, ensure_ascii=False, indent=2),
                system_prompt=(
                    "你是防汛应急预案生成智能体。"
                    "LLM 是本节点的主生成者；template_reference 是业务边界和最低兜底，不要只改写模板措辞。"
                    "若 evidence 非空，请尽量依据 evidence 生成措施，并在 summary 或 citations 中体现 [1][2] 引用。"
                    "memory_context 可用于延续用户偏好、历史处置经验和已知业务约束，但不得替代当前风险评估。"
                    "若 evidence 为空，必须保持保守，不得编造制度来源。"
                    "请基于风险评估和模板参考，输出严格 JSON。"
                    "字段必须包含：plan_name, trigger_conditions, summary, actions, resources, "
                    "notifications, citations。"
                    "actions 中每项至少包含 action_type, description, priority, responsible_dept, deadline_minutes。"
                    "resources 中每项至少包含 resource_type, resource_name, quantity, "
                    "source_location, target_location, eta_minutes。"
                    "notifications 中每项至少包含 target, channel, content, status。"
                    "citations 中每项至少包含 citation_id，可包含 document_title, source_uri, content。"
                    f"{_PLAN_OUTPUT_HARNESS.schema_instruction()}"
                    "不得输出与防汛无关内容。"
                ),
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = getattr(response, "content", "")
            harness_result = _PLAN_OUTPUT_HARNESS.parse(content)
            if harness_result.ok and harness_result.payload is not None:
                plan = _plan_from_model_payload(
                    harness_result.payload,
                    fallback_plan=plan,
                    plan_id=plan_id,
                    level=level,
                    session_id=str(state.get("session_id", "")),
                    template=template,
                )
                message = f"已生成预案 {plan.plan_name}，包含 {len(plan.actions)} 项措施"
            elif harness_result.issues:
                logger.warning(
                    "plan generator LLM output failed harness validation: %s",
                    "; ".join(harness_result.issues[:5]),
                )
        except Exception:
            message = f"已生成预案 {plan.plan_name}"

    return {
        "emergency_plan": plan,
        "current_agent": "plan_generator",
        "messages": [{"role": "plan_generator", "content": message}],
    }
