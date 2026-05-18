from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agents._contract import AgentContract, register


class SafetyCheckerIn(BaseModel):
    emergency_plan: dict[str, Any] = {}
    risk_assessment: dict[str, Any] = {}


class SafetyCheckerOut(BaseModel):
    safety_check_result: dict[str, Any] = {}
    pending_approvals: list[Any] = []


register(AgentContract(
    agent_name="safety_checker",
    input_model=SafetyCheckerIn,
    output_model=SafetyCheckerOut,
    required_input_keys=[],
))
