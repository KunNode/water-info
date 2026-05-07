"""Small harness for validating structured LLM output."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.utils.json_parser import extract_json

PayloadT = TypeVar("PayloadT", bound=BaseModel)


@dataclass(frozen=True)
class HarnessResult(Generic[PayloadT]):
    """Parsed structured output plus validation issues."""

    payload: PayloadT | None = None
    raw_content: str = ""
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.payload is not None and not self.issues


class StructuredOutputHarness(Generic[PayloadT]):
    """Constrain an LLM response to a Pydantic model."""

    def __init__(self, payload_model: type[PayloadT], *, name: str | None = None) -> None:
        self.payload_model = payload_model
        self.name = name or payload_model.__name__

    def schema_instruction(self) -> str:
        schema = self.payload_model.model_json_schema()
        return (
            f"输出必须是一个 JSON object，且必须严格符合 {self.name} JSON Schema；"
            "不要输出 Markdown、解释文字或 schema 之外的字段。"
            f"JSON Schema: {json.dumps(schema, ensure_ascii=False, separators=(',', ':'))}"
        )

    def parse(self, content: str) -> HarnessResult[PayloadT]:
        raw_content = str(content or "")
        parsed = extract_json(raw_content)
        if not isinstance(parsed, dict):
            return HarnessResult(
                raw_content=raw_content,
                issues=["模型输出不是可解析的 JSON object"],
            )

        try:
            return HarnessResult(
                payload=self.payload_model.model_validate(parsed),
                raw_content=raw_content,
            )
        except ValidationError as exc:
            issues = [
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            ]
            return HarnessResult(raw_content=raw_content, issues=issues)
