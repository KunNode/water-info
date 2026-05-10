"""Supervisor structured routing schemas."""

from __future__ import annotations

import uuid
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class SafetyLevel(str, Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class RoutingDecision(BaseModel):
    agent_run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent: str
    next_agent: str
    required_context: list[str] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)
    reasoning: str
    safety_level: SafetyLevel = SafetyLevel.NORMAL
    human_confirmation_required: bool = False

    @model_validator(mode="after")
    def _require_confirmation_for_high_safety(self) -> "RoutingDecision":
        if self.safety_level in {SafetyLevel.HIGH, SafetyLevel.CRITICAL}:
            self.human_confirmation_required = True
        return self
