"""Standardized agent output schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.state import RiskLevel


class RiskAssessorOutput(BaseModel):
    risk_level: RiskLevel
    risk_score: float = Field(ge=0.0, le=1.0)
    affected_stations: list[str]
    response_level: str
    reasoning: str
    citations: list[dict] = Field(default_factory=list)


class PlanGeneratorOutput(BaseModel):
    actions: list[dict]
    resources: list[dict]
    notifications: list[dict]
    trigger_conditions: str
    citations: list[dict] = Field(default_factory=list)


class ResourceAllocationOutput(BaseModel):
    resource_id: str
    quantity: int = Field(gt=0)
    status: str
    source_location: str
    target_location: str


class ResourceDispatcherOutput(BaseModel):
    resource_plan: list[ResourceAllocationOutput]
    dispatch_id: str | None = None


class ExecutionMonitorOutput(BaseModel):
    progress_pct: float = Field(ge=0.0, le=100.0)
    blocked_actions: list[dict] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
