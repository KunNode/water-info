"""Audit record models for platform-kernel observability."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class AgentRunRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    agent_run_id: str
    agent_name: str
    input_state_json: dict
    output_state_json: dict | None = None
    status: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    error_message: str | None = None


class ToolCallRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_run_id: str
    tool_name: str
    input_json: dict
    output_json: dict | None = None
    success: bool
    latency_ms: int
    error_message: str | None = None


class EvidenceTraceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    citation_id: str
    document_id: str
    chunk_id: str
    score: float
    used_by_agent: str
    used_in_field: str


class DecisionLogRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    decision_type: str
    decision_json: dict
    evidence_ids: list[str] = Field(default_factory=list)
    human_approved: bool | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None


class SkillRunRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    skill_id: str
    skill_version: str
    session_id: str
    agent_run_id: str
    input_json: dict
    output_json: dict | None = None
    quality_check_result: dict | list | None = None
