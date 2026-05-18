from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agents._contract import AgentContract, register


class PlanGeneratorIn(BaseModel):
    risk_assessment: dict[str, Any]
    evidence_context: list[Any] = []


class PlanGeneratorOut(BaseModel):
    emergency_plan: dict[str, Any] = {}


register(AgentContract(
    agent_name="plan_generator",
    input_model=PlanGeneratorIn,
    output_model=PlanGeneratorOut,
    required_input_keys=["risk_assessment", "evidence_context"],
))
