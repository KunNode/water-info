"""Safety checker agent for high-risk actions."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.state import to_plain_data

HIGH_RISK_ACTIONS = {
    "evacuation",
    "road_closure",
    "service_suspension",
    "dispatch_approval",
    "external_notification",
    "level_escalation",
}


class SafetyCheckResult(BaseModel):
    safe_to_proceed: bool
    risk_factors: list[str] = Field(default_factory=list)
    required_approvals: list[str] = Field(default_factory=list)
    reasoning: str = ""


def _extract_actions(state: dict) -> list[dict]:
    actions: list[dict] = []
    plan = state.get("emergency_plan")
    for action in getattr(plan, "actions", []) if plan else []:
        actions.append(to_plain_data(action))
    for order in state.get("dispatch_orders") or []:
        actions.append({**order, "action_type": "dispatch_approval"})
    for notification in state.get("notifications") or []:
        actions.append({**to_plain_data(notification), "action_type": "external_notification"})
    return actions


async def safety_checker_node(state: dict) -> dict:
    actions = _extract_actions(state)
    high_risk = [
        action for action in actions
        if str(action.get("action_type") or action.get("type") or "") in HIGH_RISK_ACTIONS
    ]
    result = SafetyCheckResult(
        safe_to_proceed=not high_risk,
        risk_factors=[str(action.get("description") or action.get("action_type")) for action in high_risk],
        required_approvals=["commander"] if high_risk else [],
        reasoning="高风险动作需人工审批" if high_risk else "未发现高风险动作",
    )
    pending = [
        {
            "action_type": str(action.get("action_type")),
            "action_payload": action,
            "status": "pending",
            "reason": "高风险动作需人工审批",
        }
        for action in high_risk
    ]
    return {
        "current_agent": "safety_checker",
        "safety_check_result": result.model_dump(mode="json"),
        "pending_approvals": pending,
    }
