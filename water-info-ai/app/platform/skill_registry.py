"""Skill registry for declarative workflow definitions."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.skills.schema import SkillDefinition

logger = logging.getLogger(__name__)


def _default_skills_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "skills"


def _load_yaml_like(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(text)
        except Exception as exc:
            raise ValueError(f"unable to parse skill file {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"skill file {path} did not contain an object")
        return data


class SkillRegistry:
    def __init__(self, skills_dir: str | Path | None = None):
        self.skills_dir = Path(skills_dir) if skills_dir is not None else _default_skills_dir()
        self._skills: dict[str, SkillDefinition] = {}
        self._intent_index: dict[str, SkillDefinition] = {}

    def load_all(self) -> None:
        self._skills.clear()
        self._intent_index.clear()
        for path in sorted(self.skills_dir.glob("*.yaml")):
            try:
                skill = SkillDefinition.model_validate(_load_yaml_like(path))
            except Exception as exc:
                logger.warning("invalid skill definition excluded: %s (%s)", path, exc)
                continue
            self._skills[skill.id] = skill
            for intent in skill.trigger_intents:
                self._intent_index[intent] = skill

    def lookup_by_intent(self, intent: str) -> SkillDefinition | None:
        return self._intent_index.get(intent)

    def get_skill(self, skill_id: str) -> SkillDefinition | None:
        return self._skills.get(skill_id)

    @property
    def skills(self) -> dict[str, SkillDefinition]:
        return dict(self._skills)


_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
