"""Agent output schema validation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from app.schemas.agent_outputs import (
    ExecutionMonitorOutput,
    PlanGeneratorOutput,
    ResourceDispatcherOutput,
    RiskAssessorOutput,
)

logger = logging.getLogger(__name__)


SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "risk_assessor": RiskAssessorOutput,
    "plan_generator": PlanGeneratorOutput,
    "resource_dispatcher": ResourceDispatcherOutput,
    "execution_monitor": ExecutionMonitorOutput,
}


@dataclass
class OutputValidationResult:
    valid: bool
    validated_output: BaseModel | None
    raw_output: Any
    errors: list[str] = field(default_factory=list)


async def validate_agent_output(
    agent_name: str,
    raw_output: dict,
    schema_registry: dict[str, type[BaseModel]] | None = None,
) -> OutputValidationResult:
    """Validate an agent payload and return a graceful degradation result."""
    registry = schema_registry or SCHEMA_REGISTRY
    schema = registry.get(agent_name)
    if schema is None:
        return OutputValidationResult(valid=True, validated_output=None, raw_output=raw_output)

    try:
        validated = schema.model_validate(raw_output)
        return OutputValidationResult(valid=True, validated_output=validated, raw_output=raw_output)
    except ValidationError as exc:
        errors = [f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in exc.errors()]
        logger.warning("agent output validation failed for %s: %s", agent_name, errors)
        return OutputValidationResult(
            valid=False,
            validated_output=None,
            raw_output=raw_output,
            errors=errors,
        )
