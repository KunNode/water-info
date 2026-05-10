"""Human approval workflow for high-risk platform actions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

HIGH_RISK_ACTION_TYPES = {
    "dispatch_approval",
    "external_notification",
    "level_escalation",
    "evacuation",
    "road_closure",
    "service_suspension",
}


class PendingApproval(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str
    action_payload: dict
    evidence: list[dict] = Field(default_factory=list)
    safety_check_result: dict | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    timeout_minutes: int = 30
    status: str = "pending"
    approval_decision: dict | None = None


class ApprovalDecision(BaseModel):
    approved: bool
    approver_id: str
    reason: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HumanInTheLoopGateway:
    def __init__(self):
        self._pending: dict[str, PendingApproval] = {}

    async def submit_for_approval(self, action: PendingApproval) -> str:
        action.status = "pending"
        self._pending[action.id] = action
        return action.id

    async def approve(self, approval_id: str, decision: ApprovalDecision) -> None:
        approval = self._pending[approval_id]
        approval.status = "approved"
        approval.approval_decision = decision.model_dump(mode="json")

    async def reject(self, approval_id: str, decision: ApprovalDecision) -> None:
        approval = self._pending[approval_id]
        approval.status = "rejected"
        approval.approval_decision = decision.model_dump(mode="json")

    async def check_timeout(self, approval_id: str) -> bool:
        approval = self._pending[approval_id]
        timed_out = datetime.now(UTC) >= approval.created_at + timedelta(minutes=approval.timeout_minutes)
        if timed_out and approval.status == "pending":
            approval.status = "escalated"
        return timed_out

    def get(self, approval_id: str) -> PendingApproval:
        return self._pending[approval_id]
