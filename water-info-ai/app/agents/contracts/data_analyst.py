from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agents._contract import AgentContract, register


class DataAnalystIn(BaseModel):
    user_query: str


class DataAnalystOut(BaseModel):
    data_summary: str = ""
    overview_data: dict[str, Any] = {}
    weather_forecast: dict[str, Any] = {}
    focus_station: dict[str, Any] = {}


register(AgentContract(
    agent_name="data_analyst",
    input_model=DataAnalystIn,
    output_model=DataAnalystOut,
    required_input_keys=["user_query"],
))
