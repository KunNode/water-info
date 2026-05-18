"""Agent input/output contract registry.

When ``AGENT_CONTRACTS_ENABLED=true``, ``audited_agent`` validates each
node's input state and output state against the registered contract.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


@dataclass
class AgentContract:
    agent_name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    required_input_keys: list[str] = field(default_factory=list)


_REGISTRY: dict[str, AgentContract] = {}


def register(contract: AgentContract) -> None:
    _REGISTRY[contract.agent_name] = contract


def get_contract(agent_name: str) -> AgentContract | None:
    return _REGISTRY.get(agent_name)


def all_contracts() -> dict[str, AgentContract]:
    return dict(_REGISTRY)


def validate_input(agent_name: str, state: dict) -> tuple[bool, list[str]]:
    contract = get_contract(agent_name)
    if contract is None:
        return True, []
    # Check required keys are present
    for key in contract.required_input_keys:
        if key not in state or state[key] is None:
            return False, [f"missing required key: {key}"]
    # Validate against Pydantic model
    try:
        contract.input_model.model_validate(_subset(state, contract.input_model))
        return True, []
    except ValidationError as exc:
        return False, _format_errors(exc)


def validate_output(agent_name: str, update: dict) -> tuple[bool, list[str]]:
    contract = get_contract(agent_name)
    if contract is None:
        return True, []
    try:
        contract.output_model.model_validate(_subset(update, contract.output_model))
        return True, []
    except ValidationError as exc:
        return False, _format_errors(exc)


def _subset(data: dict, model: type[BaseModel]) -> dict:
    """Extract only the keys that the model declares."""
    fields = model.model_fields
    return {k: v for k, v in data.items() if k in fields}


def _format_errors(exc: ValidationError) -> list[str]:
    return [f"{e['loc']}: {e['msg']}" for e in exc.errors()]
