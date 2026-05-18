from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agents._contract import AgentContract, register


class ResourceDispatcherIn(BaseModel):
    emergency_plan: dict[str, Any]


class ResourceDispatcherOut(BaseModel):
    resource_plan: list[Any] = []
    dispatch_orders: list[Any] = []


register(AgentContract(
    agent_name="resource_dispatcher",
    input_model=ResourceDispatcherIn,
    output_model=ResourceDispatcherOut,
    required_input_keys=["emergency_plan"],
))
