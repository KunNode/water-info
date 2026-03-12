"""Smoke tests for tool registration."""

from __future__ import annotations

from app.tools.data_tools import data_collection_tools
from app.tools.plan_tools import plan_generation_tools
from app.tools.risk_tools import risk_assessment_tools


def _tool_names(tools: list) -> set[str]:
    return {tool.name for tool in tools}


def test_data_tools_are_registered():
    names = _tool_names(data_collection_tools)
    assert "fetch_flood_overview" in names
    assert "fetch_station_observations" in names
    assert "fetch_active_alarms" in names


def test_risk_tools_are_registered():
    names = _tool_names(risk_assessment_tools)
    assert names == {
        "calculate_water_level_risk",
        "calculate_rainfall_risk",
        "calculate_composite_risk",
    }


def test_plan_tools_are_registered():
    names = _tool_names(plan_generation_tools)
    assert names == {
        "generate_plan_id",
        "get_response_template",
        "lookup_emergency_contacts",
    }
