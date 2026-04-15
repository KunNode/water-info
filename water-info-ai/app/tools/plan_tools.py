"""Plan generation helper tools."""

from __future__ import annotations

import json

from app.plan import generate_plan_id as _generate_plan_id, get_response_template as _get_response_template
from app.tools.simple_tool import SimpleTool


def _plan_id(_: dict) -> str:
    return json.dumps({"plan_id": _generate_plan_id()}, ensure_ascii=False)


def _template(payload: dict) -> str:
    level = str(payload.get("risk_level", "low"))
    return json.dumps(_get_response_template(level), ensure_ascii=False)


def _contacts(payload: dict) -> str:
    level = str(payload.get("risk_level", "low"))
    contacts = {
        "critical": ["省防汛指挥部", "市应急管理局", "武警支队"],
        "high": ["市防汛指挥部", "区应急管理局"],
        "moderate": ["区防汛办", "水务局"],
        "low": ["水务局值班室"],
        "none": ["值班员"],
    }
    return json.dumps({"contacts": contacts.get(level, contacts["low"])}, ensure_ascii=False)


generate_plan_id = SimpleTool("generate_plan_id", _plan_id)
get_response_template = SimpleTool("get_response_template", _template)
lookup_emergency_contacts = SimpleTool("lookup_emergency_contacts", _contacts)

plan_generation_tools = [
    generate_plan_id,
    get_response_template,
    lookup_emergency_contacts,
]
