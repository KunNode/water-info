"""Tests for structured LLM output harness."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.utils.llm_output_harness import StructuredOutputHarness


class HarnessExamplePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1)
    items: list[str] = Field(min_length=1)


def test_harness_accepts_schema_matching_json_object():
    harness = StructuredOutputHarness(HarnessExamplePayload)

    result = harness.parse('{"title":"防汛预案","items":["巡查"]}')

    assert result.ok
    assert result.payload is not None
    assert result.payload.title == "防汛预案"


def test_harness_rejects_non_json_output():
    harness = StructuredOutputHarness(HarnessExamplePayload)

    result = harness.parse("这里是一段自然语言，不是 JSON。")

    assert not result.ok
    assert result.payload is None
    assert "JSON object" in result.issues[0]


def test_harness_rejects_schema_extra_fields():
    harness = StructuredOutputHarness(HarnessExamplePayload)

    result = harness.parse('{"title":"防汛预案","items":["巡查"],"extra":"不允许"}')

    assert not result.ok
    assert result.payload is None
    assert any("extra" in issue for issue in result.issues)


def test_harness_instruction_contains_json_schema():
    harness = StructuredOutputHarness(HarnessExamplePayload, name="HarnessExamplePayload")

    instruction = harness.schema_instruction()

    assert "HarnessExamplePayload" in instruction
    assert "JSON Schema" in instruction
    assert "title" in instruction
