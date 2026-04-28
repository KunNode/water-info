"""Background risk scan scheduler."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from app.config import get_settings
from app.database import get_db_service
from app.graph import risk_event_graph, risk_only_graph
from app.services.assessment_writer import write_assessment

logger = logging.getLogger(__name__)


class RiskScanScheduler:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._task: asyncio.Task | None = None
        self._running = False
        self._semaphore = asyncio.Semaphore(2)
        self._debounce: dict[tuple[str, str], float] = {}

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        if self._settings.risk_scan_periodic_enabled:
            self._task = asyncio.create_task(self._periodic_loop(), name="risk-scan-periodic")
            logger.info("Risk scan scheduler started, interval=%s minutes", self._settings.risk_scan_periodic_minutes)
        else:
            logger.info("Risk scan scheduler periodic scan disabled")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def trigger_event(self, station_id: str, metric_type: str, level: str) -> bool:
        key = (station_id, metric_type)
        now = time.monotonic()
        last = self._debounce.get(key, 0.0)
        if now - last < self._settings.risk_scan_event_debounce_seconds:
            logger.info("Risk scan event debounced: station=%s metric=%s", station_id, metric_type)
            return False
        self._debounce[key] = now
        asyncio.create_task(self._event_scan(station_id, metric_type, level))
        return True

    async def _periodic_loop(self) -> None:
        while self._running:
            try:
                await self._periodic_scan()
            except Exception as exc:
                logger.warning("Periodic risk scan failed: %s", exc, exc_info=True)
            await asyncio.sleep(max(60, self._settings.risk_scan_periodic_minutes * 60))

    async def _periodic_scan(self) -> None:
        async with self._semaphore:
            stations = await get_db_service().list_active_stations()
            if not stations:
                return
            state = {
                "session_id": f"risk-periodic-{uuid.uuid4()}",
                "user_query": "请对当前全域防汛态势做一次定时 AI 风险巡检。",
                "intent": "risk_assessment",
                "messages": [{"role": "system", "content": "periodic risk scan"}],
                "iteration": 0,
            }
            result = await asyncio.wait_for(risk_only_graph.ainvoke(state), timeout=60)
            await write_assessment(result, source="PERIODIC", station_id=str(stations[0]["id"]))
            logger.info("Periodic risk scan completed for %s active stations", len(stations))

    async def _event_scan(self, station_id: str, metric_type: str, level: str) -> None:
        try:
            async with self._semaphore:
                state = {
                    "session_id": f"risk-event-{uuid.uuid4()}",
                    "user_query": f"站点 {station_id} 的 {metric_type} 触发 {level} 告警，请研判当前风险并给出处置建议。",
                    "intent": "plan_generation",
                    "focus_station_query": station_id,
                    "messages": [{"role": "system", "content": "event risk scan"}],
                    "iteration": 0,
                }
                result = await asyncio.wait_for(risk_event_graph.ainvoke(state), timeout=60)
                await write_assessment(result, source="EVENT", station_id=station_id, metric_type=metric_type)
                logger.info("Event risk scan completed: station=%s metric=%s level=%s", station_id, metric_type, level)
        except Exception as exc:
            logger.warning("Event risk scan failed: station=%s metric=%s error=%s", station_id, metric_type, exc, exc_info=True)


_scheduler: RiskScanScheduler | None = None


def get_risk_scan_scheduler() -> RiskScanScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = RiskScanScheduler()
    return _scheduler
