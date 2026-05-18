from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agents._contract import AgentContract, register


class NotificationIn(BaseModel):
    emergency_plan: dict[str, Any]


class NotificationOut(BaseModel):
    notifications: list[Any] = []


register(AgentContract(
    agent_name="notification",
    input_model=NotificationIn,
    output_model=NotificationOut,
    required_input_keys=["emergency_plan"],
))
