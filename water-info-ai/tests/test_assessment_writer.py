"""Tests for serialising AI assessment payloads."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.services.assessment_writer import write_assessment
from app.state import RiskAssessment, RiskLevel, to_plain_data


def test_to_plain_data_serialises_decimal_and_datetime():
    payload = {
        "level": RiskLevel.HIGH,
        "score": Decimal("82.5"),
        "count": Decimal("8"),
        "at": datetime(2026, 4, 27, 10, 0, 0),
        "items": (Decimal("1.25"), RiskLevel.LOW),
    }

    assert to_plain_data(payload) == {
        "level": "high",
        "score": 82.5,
        "count": 8,
        "at": "2026-04-27T10:00:00",
        "items": [1.25, "low"],
    }


@pytest.mark.asyncio
async def test_write_assessment_payload_is_json_ready(monkeypatch):
    captured = {}

    class FakePlatformClient:
        async def upsert_ai_assessment(self, payload: dict) -> dict:
            captured.update(payload)
            return {"code": 200}

    monkeypatch.setattr("app.services.assessment_writer.get_platform_client", lambda: FakePlatformClient())

    state = {
        "risk_assessment": RiskAssessment(
            risk_level=RiskLevel.HIGH,
            risk_score=82.5,
            affected_stations=["station-001"],
            key_risks=["水位上涨"],
        ),
        "overview_data": {
            "stations": [{"id": "station-001", "water_level": Decimal("4.8")}],
            "checked_at": datetime(2026, 4, 27, 10, 0, 0),
        },
        "final_response": "风险较高，建议加强巡查。",
    }

    response = await write_assessment(state, source="periodic")

    assert response == {"code": 200}
    assert captured["stationId"] == "station-001"
    assert captured["level"] == "high"
    assert captured["raw"]["overview_data"]["stations"][0]["water_level"] == 4.8
    assert captured["raw"]["overview_data"]["checked_at"] == "2026-04-27T10:00:00"
