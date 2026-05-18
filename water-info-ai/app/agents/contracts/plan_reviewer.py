from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agents._contract import AgentContract, register


class PlanReviewerIn(BaseModel):
    emergency_plan: dict[str, Any] = {}
    evidence_context: list[Any] = []


class PlanReviewerOut(BaseModel):
    compliance_result: dict[str, Any] = {}
    evidence_context: list[Any] = []
    evidence: list[Any] = []


register(AgentContract(
    agent_name="plan_reviewer",
    input_model=PlanReviewerIn,
    output_model=PlanReviewerOut,
    required_input_keys=[],
))
