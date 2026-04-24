"""Shared state and domain models for the LangGraph workflow."""

from __future__ import annotations

import operator
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Annotated, TypedDict


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskAssessment:
    risk_level: RiskLevel = RiskLevel.NONE
    risk_score: float = 0.0
    affected_stations: list[str] = field(default_factory=list)
    key_risks: list[str] = field(default_factory=list)
    trend: str | None = None
    reasoning: str | None = None
    response_level: str | None = None


@dataclass
class EmergencyAction:
    action_id: str
    action_type: str
    description: str
    priority: int = 3
    responsible_dept: str = ""
    deadline_minutes: int | None = None
    status: str = "pending"


@dataclass
class ResourceAllocation:
    resource_type: str
    resource_name: str
    quantity: int
    source_location: str = ""
    target_location: str = ""
    eta_minutes: int | None = None
    status: str = "pending"


@dataclass
class NotificationRecord:
    target: str
    channel: str
    content: str
    status: str = "pending"
    sent_at: str | None = None


@dataclass
class Evidence:
    citation_id: str
    content: str
    document_title: str
    source_uri: str = ""
    heading_path: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class EmergencyPlan:
    plan_id: str
    plan_name: str
    risk_level: RiskLevel | str = RiskLevel.NONE
    trigger_conditions: str = ""
    status: str = "draft"
    session_id: str = ""
    summary: str = ""
    actions: list[EmergencyAction] = field(default_factory=list)
    resources: list[ResourceAllocation] = field(default_factory=list)
    notifications: list[NotificationRecord] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)


class FloodGraphState(TypedDict, total=False):
    session_id: str
    user_query: str
    messages: Annotated[list[dict], operator.add]
    iteration: int
    current_agent: str
    next_agent: str
    intent: str
    supervisor_reasoning: str
    focus_station_query: str
    focus_station: dict
    data_summary: str
    overview_data: dict
    weather_forecast: dict
    risk_assessment: RiskAssessment
    emergency_plan: EmergencyPlan
    resource_plan: list[ResourceAllocation]
    notifications: list[NotificationRecord]
    evidence: list[Evidence]
    final_response: str
    error: str


def to_plain_data(value):
    """Convert domain models to JSON-serialisable structures."""
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_plain_data(val) for key, val in asdict(value).items()}
    if isinstance(value, list):
        return [to_plain_data(item) for item in value]
    if isinstance(value, dict):
        return {key: to_plain_data(val) for key, val in value.items()}
    return value
