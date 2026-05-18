from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agents._contract import AgentContract, register


class RiskAssessorIn(BaseModel):
    data_summary: str


class RiskAssessorOut(BaseModel):
    risk_assessment: dict[str, Any] = {}


register(AgentContract(
    agent_name="risk_assessor",
    input_model=RiskAssessorIn,
    output_model=RiskAssessorOut,
    required_input_keys=["data_summary"],
))
