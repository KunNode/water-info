from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agents._contract import AgentContract, register


class ExecutionMonitorIn(BaseModel):
    session_id: str


class ExecutionMonitorOut(BaseModel):
    execution_progress: dict[str, Any] = {}


register(AgentContract(
    agent_name="execution_monitor",
    input_model=ExecutionMonitorIn,
    output_model=ExecutionMonitorOut,
    required_input_keys=["session_id"],
))
