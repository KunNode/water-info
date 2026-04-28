"""Risk scan trigger API."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.services.risk_scan_scheduler import get_risk_scan_scheduler

router = APIRouter(prefix="/api/v1/flood/risk-scan", tags=["risk-scan"])


class RiskScanTriggerRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    station_id: str = Field(validation_alias=AliasChoices("station_id", "stationId"))
    metric_type: str = Field(validation_alias=AliasChoices("metric_type", "metricType"))
    level: str


@router.post("/trigger")
async def trigger_risk_scan(request: RiskScanTriggerRequest) -> dict:
    accepted = await get_risk_scan_scheduler().trigger_event(
        request.station_id,
        request.metric_type,
        request.level,
    )
    return {"accepted": accepted}
