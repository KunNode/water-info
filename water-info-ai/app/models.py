"""Pydantic request/response models."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class FloodQueryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str = Field(..., description="用户请求，如：'分析当前水情并生成应急预案'")
    session_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("session_id", "sessionId"),
        serialization_alias="session_id",
    )


class FloodQueryResponse(BaseModel):
    session_id: str
    response: str
    risk_level: str | None = None
    risk_score: float | None = None
    plan_id: str | None = None
    plan_name: str | None = None
    actions_count: int = 0
    resources_count: int = 0
    notifications_count: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "water-info-ai"
    version: str = "1.0.0"


class PlanDetailResponse(BaseModel):
    plan_id: str
    plan_name: str
    risk_level: str
    trigger_conditions: str
    status: str
    session_id: str
    summary: str
    actions: list[dict]
    resources: list[dict]
    notifications: list[dict]
    created_at: str | None = None


class PlanExecuteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action_ids: list[str] | None = Field(
        default=None,
        validation_alias=AliasChoices("action_ids", "actionIds"),
        serialization_alias="action_ids",
    )


class PlanExecuteResponse(BaseModel):
    plan_id: str
    status: str
    executed_actions: int
    message: str


class SessionResponse(BaseModel):
    session_id: str
    plans: list[dict]
    created_at: str | None = None
