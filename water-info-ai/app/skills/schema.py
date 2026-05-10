"""Skill definition schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QualityGate(BaseModel):
    name: str
    check_type: str
    target_field: str
    condition: str
    threshold: float | None = None


class QualityGateResult(BaseModel):
    name: str
    passed: bool
    detail: str = ""


class SkillDefinition(BaseModel):
    id: str
    name: str
    version: str
    trigger_intents: list[str]
    required_inputs: list[str]
    required_tools: list[str]
    agent_sequence: list[str]
    output_schema: str
    quality_gates: list[QualityGate] = Field(default_factory=list)
    fallback_strategy: str = "degrade"


class SkillRunResult(BaseModel):
    skill_id: str
    skill_version: str
    quality_results: list[QualityGateResult] = Field(default_factory=list)
    fallback_executed: str | None = None
