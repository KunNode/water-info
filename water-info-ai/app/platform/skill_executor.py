"""Skill-driven workflow execution helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.skills.schema import QualityGate, QualityGateResult, SkillDefinition, SkillRunResult
from app.state import FloodGraphState

AgentCallable = Callable[[FloodGraphState], Awaitable[dict] | dict]


def _read_path(state: dict, dotted_path: str) -> Any:
    value: Any = state
    for part in dotted_path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
        if value is None:
            return None
    return value


class SkillExecutor:
    async def execute(
        self,
        skill: SkillDefinition,
        state: FloodGraphState,
        agent_registry: dict[str, AgentCallable],
    ) -> tuple[FloodGraphState, SkillRunResult]:
        current: FloodGraphState = dict(state)
        current["active_skill_id"] = skill.id
        current["skill_agent_sequence"] = list(skill.agent_sequence)

        for agent_name in skill.agent_sequence:
            agent = agent_registry.get(agent_name)
            if agent is None:
                continue
            update = agent(current)
            if hasattr(update, "__await__"):
                update = await update  # type: ignore[assignment]
            if isinstance(update, dict):
                current.update(update)

        quality_results = self.evaluate_quality_gates(skill, current)
        current["skill_quality_results"] = [item.model_dump(mode="json") for item in quality_results]
        fallback = None if all(item.passed for item in quality_results) else skill.fallback_strategy
        return current, SkillRunResult(
            skill_id=skill.id,
            skill_version=skill.version,
            quality_results=quality_results,
            fallback_executed=fallback,
        )

    def evaluate_quality_gates(self, skill: SkillDefinition, state: FloodGraphState) -> list[QualityGateResult]:
        return [self._evaluate_gate(gate, state) for gate in skill.quality_gates]

    def _evaluate_gate(self, gate: QualityGate, state: dict) -> QualityGateResult:
        value = _read_path(state, gate.target_field)
        if gate.check_type == "field_present":
            passed = value is not None
        elif gate.check_type == "threshold":
            size = len(value) if hasattr(value, "__len__") and not isinstance(value, (str, bytes)) else float(value or 0)
            threshold = gate.threshold if gate.threshold is not None else 0
            passed = size >= threshold if ">=" in gate.condition else size > threshold
        else:
            passed = value is not None
        return QualityGateResult(name=gate.name, passed=bool(passed), detail="" if passed else f"{gate.target_field} failed")
