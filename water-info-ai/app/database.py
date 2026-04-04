"""PostgreSQL async database service for water data and plan persistence."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import asyncpg

from app.config import get_settings


class DatabaseService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._pool: asyncpg.Pool | None = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self._settings.pg_host,
                port=self._settings.pg_port,
                database=self._settings.pg_database,
                user=self._settings.pg_user,
                password=self._settings.pg_password,
                min_size=2,
                max_size=10,
                command_timeout=self._settings.db_command_timeout,
            )
        return self._pool

    async def _fetch(self, query: str, *args) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    async def _fetchrow(self, query: str, *args) -> dict[str, Any] | None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def _fetchval(self, query: str, *args) -> Any:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    # ── Stations ──────────────────────────────────────────────────────────────

    async def get_station_with_latest_data(self) -> list[dict]:
        return await self._fetch("""
            WITH latest_obs AS (
                SELECT DISTINCT ON (station_id, metric_type)
                    station_id, metric_type, value, observed_at
                FROM observation
                ORDER BY station_id, metric_type, observed_at DESC
            )
            SELECT
                s.id, s.code, s.name, s.type, s.river_basin, s.admin_region,
                s.lat, s.lon, s.status,
                wl.value  AS water_level,
                wl.observed_at AS water_level_time,
                rf.value  AS rainfall,
                rf.observed_at AS rainfall_time,
                fl.value  AS flow_rate,
                fl.observed_at AS flow_rate_time
            FROM station s
            LEFT JOIN latest_obs wl ON wl.station_id = s.id AND wl.metric_type = 'WATER_LEVEL'
            LEFT JOIN latest_obs rf ON rf.station_id = s.id AND rf.metric_type = 'RAINFALL'
            LEFT JOIN latest_obs fl ON fl.station_id = s.id AND fl.metric_type = 'FLOW'
            ORDER BY s.code
        """)

    # ── Observations ──────────────────────────────────────────────────────────

    async def get_rainfall_stats(self, station_id: str) -> dict | None:
        return await self._fetchrow("""
            SELECT
                COALESCE(SUM(CASE WHEN observed_at >= NOW() - INTERVAL '1 hour'  THEN value ELSE 0 END), 0) AS rainfall_1h,
                COALESCE(SUM(CASE WHEN observed_at >= NOW() - INTERVAL '6 hours' THEN value ELSE 0 END), 0) AS rainfall_6h,
                COALESCE(SUM(CASE WHEN observed_at >= NOW() - INTERVAL '24 hours' THEN value ELSE 0 END), 0) AS rainfall_24h
            FROM observation
            WHERE station_id = $1 AND metric_type = 'RAINFALL'
              AND observed_at >= NOW() - INTERVAL '24 hours'
        """, station_id)

    # ── Alarms ────────────────────────────────────────────────────────────────

    async def get_active_alarms(self, station_id: str | None = None) -> list[dict]:
        if station_id:
            return await self._fetch("""
                SELECT a.id, a.station_id, s.name AS station_name, a.metric_type,
                       a.level, a.status, a.message, a.start_at, a.last_trigger_at
                FROM alarm a JOIN station s ON s.id = a.station_id
                WHERE a.status IN ('OPEN', 'ACK') AND a.station_id = $1
                ORDER BY a.level DESC, a.last_trigger_at DESC
            """, station_id)
        return await self._fetch("""
            SELECT a.id, a.station_id, s.name AS station_name, a.metric_type,
                   a.level, a.status, a.message, a.start_at, a.last_trigger_at
            FROM alarm a JOIN station s ON s.id = a.station_id
            WHERE a.status IN ('OPEN', 'ACK')
            ORDER BY a.level DESC, a.last_trigger_at DESC
        """)

    # ── Thresholds ────────────────────────────────────────────────────────────

    async def get_station_thresholds_summary(self) -> list[dict]:
        return await self._fetch("""
            SELECT
                s.id AS station_id, s.name AS station_name, s.code,
                MAX(CASE WHEN tr.metric_type = 'WATER_LEVEL' AND tr.level = 'WARNING'  THEN tr.threshold_value END) AS warning_level,
                MAX(CASE WHEN tr.metric_type = 'WATER_LEVEL' AND tr.level = 'CRITICAL' THEN tr.threshold_value END) AS danger_level,
                MAX(CASE WHEN tr.metric_type = 'RAINFALL'    AND tr.level = 'WARNING'  THEN tr.threshold_value END) AS rainfall_warning,
                MAX(CASE WHEN tr.metric_type = 'RAINFALL'    AND tr.level = 'CRITICAL' THEN tr.threshold_value END) AS rainfall_danger
            FROM station s
            LEFT JOIN threshold_rule tr ON tr.station_id = s.id AND tr.enabled = TRUE
            GROUP BY s.id, s.name, s.code
            ORDER BY s.code
        """)

    # ── Flood overview (composite) ────────────────────────────────────────────

    async def get_flood_situation_overview(self) -> dict:
        stations, thresholds, alarms = await asyncio.gather(
            self.get_station_with_latest_data(),
            self.get_station_thresholds_summary(),
            self.get_active_alarms(),
        )
        threshold_map = {t["station_id"]: t for t in thresholds}
        enriched = []
        for s in stations:
            t = threshold_map.get(s["id"], {})
            enriched.append({
                **s,
                "warning_level": t.get("warning_level"),
                "danger_level": t.get("danger_level"),
                "rainfall_warning": t.get("rainfall_warning"),
                "rainfall_danger": t.get("rainfall_danger"),
            })
        return {
            "stations": enriched,
            "active_alarms": alarms,
            "station_count": len(stations),
            "alarm_count": len(alarms),
        }

    # ── Plan tables DDL ───────────────────────────────────────────────────────

    async def ensure_plan_tables(self) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS emergency_plan (
                    id          BIGSERIAL PRIMARY KEY,
                    plan_id     VARCHAR(64) UNIQUE NOT NULL,
                    plan_name   VARCHAR(255) NOT NULL DEFAULT '',
                    risk_level  VARCHAR(32) NOT NULL DEFAULT 'none',
                    trigger_conditions TEXT NOT NULL DEFAULT '',
                    status      VARCHAR(32) NOT NULL DEFAULT 'draft',
                    session_id  VARCHAR(128) NOT NULL DEFAULT '',
                    summary     TEXT NOT NULL DEFAULT '',
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS emergency_action (
                    id               BIGSERIAL PRIMARY KEY,
                    plan_id          VARCHAR(64) NOT NULL REFERENCES emergency_plan(plan_id) ON DELETE CASCADE,
                    action_id        VARCHAR(64) NOT NULL DEFAULT '',
                    action_type      VARCHAR(64) NOT NULL DEFAULT '',
                    description      TEXT NOT NULL DEFAULT '',
                    priority         INT NOT NULL DEFAULT 3,
                    responsible_dept VARCHAR(128) NOT NULL DEFAULT '',
                    deadline_minutes INT,
                    status           VARCHAR(32) NOT NULL DEFAULT 'pending',
                    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS resource_allocation (
                    id               BIGSERIAL PRIMARY KEY,
                    plan_id          VARCHAR(64) NOT NULL REFERENCES emergency_plan(plan_id) ON DELETE CASCADE,
                    resource_type    VARCHAR(64) NOT NULL DEFAULT '',
                    resource_name    VARCHAR(128) NOT NULL DEFAULT '',
                    quantity         INT NOT NULL DEFAULT 0,
                    source_location  VARCHAR(255) NOT NULL DEFAULT '',
                    target_location  VARCHAR(255) NOT NULL DEFAULT '',
                    eta_minutes      INT,
                    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS notification_record (
                    id         BIGSERIAL PRIMARY KEY,
                    plan_id    VARCHAR(64) NOT NULL REFERENCES emergency_plan(plan_id) ON DELETE CASCADE,
                    target     VARCHAR(255) NOT NULL DEFAULT '',
                    channel    VARCHAR(32) NOT NULL DEFAULT 'sms',
                    content    TEXT NOT NULL DEFAULT '',
                    status     VARCHAR(32) NOT NULL DEFAULT 'pending',
                    sent_at    TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

    # ── Plan write ────────────────────────────────────────────────────────────

    async def save_emergency_plan(
        self,
        plan_id: str,
        plan_name: str,
        risk_level: str,
        trigger_conditions: str,
        status: str,
        session_id: str,
        summary: str,
        actions: list[dict],
    ) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("""
                    INSERT INTO emergency_plan
                        (plan_id, plan_name, risk_level, trigger_conditions, status, session_id, summary)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (plan_id) DO UPDATE SET
                        plan_name = EXCLUDED.plan_name, risk_level = EXCLUDED.risk_level,
                        trigger_conditions = EXCLUDED.trigger_conditions, status = EXCLUDED.status,
                        summary = EXCLUDED.summary, updated_at = NOW()
                """, plan_id, plan_name, risk_level, trigger_conditions, status, session_id, summary)

                await conn.execute("DELETE FROM emergency_action WHERE plan_id = $1", plan_id)
                for a in actions:
                    await conn.execute("""
                        INSERT INTO emergency_action
                            (plan_id, action_id, action_type, description, priority,
                             responsible_dept, deadline_minutes, status)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, plan_id, a.get("action_id", ""), a.get("action_type", ""),
                        a.get("description", ""), a.get("priority", 3),
                        a.get("responsible_dept", ""), a.get("deadline_minutes"),
                        a.get("status", "pending"))

    async def save_resource_allocations(self, plan_id: str, resources: list[dict]) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM resource_allocation WHERE plan_id = $1", plan_id)
                for r in resources:
                    await conn.execute("""
                        INSERT INTO resource_allocation
                            (plan_id, resource_type, resource_name, quantity,
                             source_location, target_location, eta_minutes)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """, plan_id, r.get("resource_type", r.get("type", "")),
                        r.get("resource_name", r.get("name", "")),
                        r.get("quantity", 0), r.get("source_location", ""),
                        r.get("target_location", ""), r.get("eta_minutes"))

    async def save_notifications(self, plan_id: str, notifications: list[dict]) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM notification_record WHERE plan_id = $1", plan_id)
                for n in notifications:
                    await conn.execute("""
                        INSERT INTO notification_record (plan_id, target, channel, content, status)
                        VALUES ($1, $2, $3, $4, $5)
                    """, plan_id, n.get("target", ""), n.get("channel", "sms"),
                        n.get("content", ""), n.get("status", "pending"))

    # ── Plan read ─────────────────────────────────────────────────────────────

    async def get_emergency_plan(self, plan_id: str) -> dict | None:
        return await self._fetchrow("""
            SELECT plan_id, plan_name, risk_level, trigger_conditions, status,
                   session_id, summary, created_at, updated_at
            FROM emergency_plan WHERE plan_id = $1
        """, plan_id)

    async def get_plan_actions(self, plan_id: str) -> list[dict]:
        return await self._fetch("""
            SELECT action_id, action_type, description, priority, responsible_dept,
                   deadline_minutes, status, created_at
            FROM emergency_action WHERE plan_id = $1 ORDER BY priority ASC
        """, plan_id)

    async def get_plan_resources(self, plan_id: str) -> list[dict]:
        return await self._fetch("""
            SELECT resource_type, resource_name, quantity, source_location,
                   target_location, eta_minutes, created_at
            FROM resource_allocation WHERE plan_id = $1
        """, plan_id)

    async def get_plan_notifications(self, plan_id: str) -> list[dict]:
        return await self._fetch("""
            SELECT target, channel, content, status, sent_at, created_at
            FROM notification_record WHERE plan_id = $1
        """, plan_id)

    async def get_plans(self, limit: int = 20, offset: int = 0) -> list[dict]:
        return await self._fetch("""
            SELECT plan_id, plan_name, risk_level, status, session_id, summary, created_at
            FROM emergency_plan ORDER BY created_at DESC LIMIT $1 OFFSET $2
        """, limit, offset)

    async def get_plan_count(self) -> int:
        return (await self._fetchval("SELECT COUNT(*) FROM emergency_plan")) or 0

    async def update_plan_status(self, plan_id: str, status: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE emergency_plan SET status = $1, updated_at = NOW() WHERE plan_id = $2",
                status, plan_id,
            )

    async def update_action_status(self, plan_id: str, action_id: str, status: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE emergency_action SET status = $1 WHERE plan_id = $2 AND action_id = $3",
                status, plan_id, action_id,
            )

    async def get_plans_by_session(self, session_id: str) -> list[dict]:
        return await self._fetch("""
            SELECT plan_id, plan_name, risk_level, status, created_at
            FROM emergency_plan WHERE session_id = $1 ORDER BY created_at DESC
        """, session_id)

    async def get_sessions(self, limit: int = 20, offset: int = 0) -> list[dict]:
        return await self._fetch("""
            SELECT session_id, MAX(created_at) AS created_at
            FROM emergency_plan GROUP BY session_id
            ORDER BY MAX(created_at) DESC LIMIT $1 OFFSET $2
        """, limit, offset)

    async def get_session_count(self) -> int:
        return (await self._fetchval("SELECT COUNT(DISTINCT session_id) FROM emergency_plan")) or 0

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None


_service: DatabaseService | None = None


def get_db_service() -> DatabaseService:
    global _service
    if _service is None:
        _service = DatabaseService()
    return _service
