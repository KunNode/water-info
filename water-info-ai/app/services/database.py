"""PostgreSQL 数据库服务

直接从 PostgreSQL 读取水务数据，供智能体工具调用。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import asyncpg
from loguru import logger

from app.config import get_settings


class DatabaseService:
    """PostgreSQL 异步数据库服务"""

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
            logger.info("PostgreSQL 连接池已创建")
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

    # ──────────────────────────────────────
    # 监测站
    # ──────────────────────────────────────

    async def get_all_stations(self) -> list[dict]:
        """获取所有监测站及其基本信息"""
        return await self._fetch("""
            SELECT id, code, name, type, river_basin, admin_region,
                   lat, lon, elevation, status, created_at, updated_at
            FROM station
            ORDER BY code
        """)

    async def get_station(self, station_id: str) -> dict | None:
        """获取单个监测站详情"""
        return await self._fetchrow("""
            SELECT id, code, name, type, river_basin, admin_region,
                   lat, lon, elevation, status, created_at, updated_at
            FROM station WHERE id = $1
        """, station_id)

    async def get_station_with_latest_data(self) -> list[dict]:
        """获取所有监测站及其最新观测数据（水位、雨量）"""
        return await self._fetch("""
            WITH latest_obs AS (
                SELECT DISTINCT ON (station_id, metric_type)
                    station_id, metric_type, value, unit, observed_at, quality_flag
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

    # ──────────────────────────────────────
    # 传感器
    # ──────────────────────────────────────

    async def get_sensors(self, station_id: str | None = None) -> list[dict]:
        """获取传感器列表"""
        if station_id:
            return await self._fetch("""
                SELECT se.id, se.station_id, s.name AS station_name, se.type,
                       se.unit, se.sampling_interval_sec, se.status, se.last_seen_at
                FROM sensor se JOIN station s ON s.id = se.station_id
                WHERE se.station_id = $1
                ORDER BY se.type
            """, station_id)
        return await self._fetch("""
            SELECT se.id, se.station_id, s.name AS station_name, se.type,
                   se.unit, se.sampling_interval_sec, se.status, se.last_seen_at
            FROM sensor se JOIN station s ON s.id = se.station_id
            ORDER BY s.code, se.type
        """)

    # ──────────────────────────────────────
    # 观测数据
    # ──────────────────────────────────────

    async def get_observations(
        self,
        station_id: str | None = None,
        metric_type: str | None = None,
        hours: int = 24,
        limit: int = 500,
    ) -> list[dict]:
        """获取观测数据"""
        conditions = ["observed_at >= $1"]
        params: list[Any] = [datetime.now() - timedelta(hours=hours)]
        idx = 2

        if station_id:
            conditions.append(f"o.station_id = ${idx}")
            params.append(station_id)
            idx += 1
        if metric_type:
            conditions.append(f"o.metric_type = ${idx}")
            params.append(metric_type)
            idx += 1

        where = " AND ".join(conditions)
        params.append(limit)
        limit_param = f"${idx}"
        return await self._fetch(f"""
            SELECT o.id, o.station_id, s.name AS station_name, o.metric_type,
                   o.value, o.unit, o.observed_at, o.quality_flag, o.source
            FROM observation o
            JOIN station s ON s.id = o.station_id
            WHERE {where}
            ORDER BY o.observed_at DESC
            LIMIT {limit_param}
        """, *params)

    async def get_water_level_trend(self, station_id: str, hours: int = 6) -> list[dict]:
        """获取指定站点的水位变化趋势"""
        return await self._fetch("""
            SELECT value, observed_at
            FROM observation
            WHERE station_id = $1 AND metric_type = 'WATER_LEVEL'
              AND observed_at >= $2
            ORDER BY observed_at ASC
        """, station_id, datetime.now() - timedelta(hours=hours))

    async def get_rainfall_stats(self, station_id: str) -> dict | None:
        """获取指定站点的1h/6h/24h累计降雨量"""
        return await self._fetchrow("""
            SELECT
                COALESCE(SUM(CASE WHEN observed_at >= NOW() - INTERVAL '1 hour'  THEN value ELSE 0 END), 0) AS rainfall_1h,
                COALESCE(SUM(CASE WHEN observed_at >= NOW() - INTERVAL '6 hours' THEN value ELSE 0 END), 0) AS rainfall_6h,
                COALESCE(SUM(CASE WHEN observed_at >= NOW() - INTERVAL '24 hours' THEN value ELSE 0 END), 0) AS rainfall_24h
            FROM observation
            WHERE station_id = $1 AND metric_type = 'RAINFALL'
              AND observed_at >= NOW() - INTERVAL '24 hours'
        """, station_id)

    # ──────────────────────────────────────
    # 告警
    # ──────────────────────────────────────

    async def get_active_alarms(self, station_id: str | None = None) -> list[dict]:
        """获取活跃告警"""
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

    async def get_alarm_statistics(self) -> dict | None:
        """获取告警统计（按等级、按状态）"""
        return await self._fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE status IN ('OPEN','ACK')) AS active_count,
                COUNT(*) FILTER (WHERE status = 'OPEN')         AS open_count,
                COUNT(*) FILTER (WHERE status = 'ACK')          AS ack_count,
                COUNT(*) FILTER (WHERE level = 'CRITICAL' AND status IN ('OPEN','ACK')) AS critical_count,
                COUNT(*) FILTER (WHERE level = 'WARNING'  AND status IN ('OPEN','ACK')) AS warning_count,
                COUNT(*) FILTER (WHERE level = 'INFO'     AND status IN ('OPEN','ACK')) AS info_count
            FROM alarm
        """)

    # ──────────────────────────────────────
    # 阈值规则
    # ──────────────────────────────────────

    async def get_threshold_rules(self, station_id: str | None = None) -> list[dict]:
        """获取阈值规则"""
        if station_id:
            return await self._fetch("""
                SELECT tr.id, tr.station_id, s.name AS station_name, tr.metric_type,
                       tr.level, tr.threshold_value, tr.duration_min, tr.rate_threshold, tr.enabled
                FROM threshold_rule tr JOIN station s ON s.id = tr.station_id
                WHERE tr.enabled = TRUE AND tr.station_id = $1
                ORDER BY tr.level DESC
            """, station_id)
        return await self._fetch("""
            SELECT tr.id, tr.station_id, s.name AS station_name, tr.metric_type,
                   tr.level, tr.threshold_value, tr.duration_min, tr.rate_threshold, tr.enabled
            FROM threshold_rule tr JOIN station s ON s.id = tr.station_id
            WHERE tr.enabled = TRUE
            ORDER BY s.code, tr.level DESC
        """)

    async def get_station_thresholds_summary(self) -> list[dict]:
        """获取每个站点的警戒/危险水位阈值汇总"""
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

    # ──────────────────────────────────────
    # 综合查询 — 防洪态势全景（一次查询获取关键信息）
    # ──────────────────────────────────────

    async def get_flood_situation_overview(self) -> dict:
        """
        防洪态势全景：一次性获取所有关键数据，减少多次查询开销。
        返回包含站点、最新观测、阈值、告警的综合数据。
        """
        stations = await self.get_station_with_latest_data()
        thresholds = await self.get_station_thresholds_summary()
        alarms = await self.get_active_alarms()
        alarm_stats = await self.get_alarm_statistics()

        # 构建阈值映射
        threshold_map = {t["station_id"]: t for t in thresholds}

        # 合并站点数据和阈值
        enriched_stations = []
        for s in stations:
            t = threshold_map.get(s["id"], {})
            enriched_stations.append({
                **s,
                "warning_level": t.get("warning_level"),
                "danger_level": t.get("danger_level"),
                "rainfall_warning": t.get("rainfall_warning"),
                "rainfall_danger": t.get("rainfall_danger"),
            })

        return {
            "stations": enriched_stations,
            "active_alarms": alarms,
            "alarm_statistics": alarm_stats or {},
            "station_count": len(stations),
            "alarm_count": len(alarms),
        }

    # ──────────────────────────────────────
    # 资源清理
    # ──────────────────────────────────────

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.info("PostgreSQL 连接池已关闭")

    # ──────────────────────────────────────
    # 预案持久化 DDL
    # ──────────────────────────────────────

    async def ensure_plan_tables(self) -> None:
        """创建预案持久化表（如果不存在）"""
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
                    version     INT NOT NULL DEFAULT 0,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            # Optimistic-lock column for human-review workflow (plan-human-review Req 1.5/3.8).
            await conn.execute("""
                DO $$ BEGIN
                    ALTER TABLE emergency_plan ADD COLUMN IF NOT EXISTS version INT NOT NULL DEFAULT 0;
                EXCEPTION WHEN others THEN NULL;
                END $$;
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

            # ── Audit tables (plan-human-review Req 7.1, 7.2, 7.8) ──
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS plan_audit_record (
                    id                BIGSERIAL PRIMARY KEY,
                    plan_id           VARCHAR(64) NOT NULL
                                      REFERENCES emergency_plan(plan_id) ON DELETE CASCADE,
                    action            VARCHAR(32) NOT NULL,
                    reviewer_user_id  VARCHAR(64) NOT NULL,
                    reviewer_username VARCHAR(255) NOT NULL,
                    reviewed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    opinion           TEXT,
                    from_status       VARCHAR(32) NOT NULL,
                    to_status         VARCHAR(32) NOT NULL,
                    from_version      INT NOT NULL,
                    to_version        INT NOT NULL
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_plan_audit_plan_time
                    ON plan_audit_record(plan_id, reviewed_at DESC)
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS plan_audit_change (
                    id              BIGSERIAL PRIMARY KEY,
                    audit_id        BIGINT NOT NULL
                                    REFERENCES plan_audit_record(id) ON DELETE CASCADE,
                    field_path      VARCHAR(255) NOT NULL,
                    change_type     VARCHAR(16)  NOT NULL,
                    old_value       TEXT,
                    new_value       TEXT,
                    old_index       INT,
                    new_index       INT
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_plan_audit_change_audit
                    ON plan_audit_change(audit_id)
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS plan_audit_draft (
                    id              BIGSERIAL PRIMARY KEY,
                    plan_id         VARCHAR(64) NOT NULL
                                    REFERENCES emergency_plan(plan_id) ON DELETE CASCADE,
                    buffered_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    reviewer_user_id  VARCHAR(64) NOT NULL,
                    reviewer_username VARCHAR(255) NOT NULL,
                    field_path      VARCHAR(255) NOT NULL,
                    change_type     VARCHAR(16)  NOT NULL,
                    old_value       TEXT,
                    new_value       TEXT,
                    old_index       INT,
                    new_index       INT
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_plan_audit_draft_plan
                    ON plan_audit_draft(plan_id, buffered_at)
            """)

            # ── Immutability triggers (plan-human-review Req 7.8, Property P5) ──
            await conn.execute("""
                CREATE OR REPLACE FUNCTION plan_audit_no_update()
                RETURNS trigger AS $$
                BEGIN
                  RAISE EXCEPTION 'plan_audit_record is immutable';
                END; $$ LANGUAGE plpgsql
            """)
            await conn.execute("""
                DROP TRIGGER IF EXISTS trg_plan_audit_record_immutable
                    ON plan_audit_record
            """)
            await conn.execute("""
                CREATE TRIGGER trg_plan_audit_record_immutable
                BEFORE UPDATE OR DELETE ON plan_audit_record
                FOR EACH ROW EXECUTE FUNCTION plan_audit_no_update()
            """)
            await conn.execute("""
                DROP TRIGGER IF EXISTS trg_plan_audit_change_immutable
                    ON plan_audit_change
            """)
            await conn.execute("""
                CREATE TRIGGER trg_plan_audit_change_immutable
                BEFORE UPDATE OR DELETE ON plan_audit_change
                FOR EACH ROW EXECUTE FUNCTION plan_audit_no_update()
            """)
            logger.info("预案持久化表已就绪")

    # ──────────────────────────────────────
    # 预案持久化写入
    # ──────────────────────────────────────

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
        """保存应急预案及其措施（事务）"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("""
                    INSERT INTO emergency_plan (plan_id, plan_name, risk_level, trigger_conditions, status, session_id, summary, version)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 0)
                    ON CONFLICT (plan_id) DO UPDATE SET
                        plan_name = EXCLUDED.plan_name,
                        risk_level = EXCLUDED.risk_level,
                        trigger_conditions = EXCLUDED.trigger_conditions,
                        status = EXCLUDED.status,
                        summary = EXCLUDED.summary,
                        updated_at = NOW()
                """, plan_id, plan_name, risk_level, trigger_conditions, status, session_id, summary)

                # 清除旧措施后重新插入
                await conn.execute("DELETE FROM emergency_action WHERE plan_id = $1", plan_id)
                for a in actions:
                    await conn.execute("""
                        INSERT INTO emergency_action (
                            plan_id, action_id, action_type, description, priority,
                            responsible_dept, deadline_minutes, status
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, plan_id, a.get("action_id", ""), a.get("action_type", ""),
                        a.get("description", ""), a.get("priority", 3),
                        a.get("responsible_dept", ""), a.get("deadline_minutes"),
                        a.get("status", "pending"))
        logger.info(f"预案 {plan_id} 已持久化（{len(actions)} 项措施）")

    async def save_resource_allocations(self, plan_id: str, resources: list[dict]) -> None:
        """保存资源调度方案（事务）"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM resource_allocation WHERE plan_id = $1", plan_id)
                for r in resources:
                    await conn.execute("""
                        INSERT INTO resource_allocation (
                            plan_id, resource_type, resource_name, quantity,
                            source_location, target_location, eta_minutes
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """, plan_id, r.get("resource_type", ""), r.get("resource_name", ""),
                        r.get("quantity", 0), r.get("source_location", ""),
                        r.get("target_location", ""), r.get("eta_minutes"))
        logger.info(f"预案 {plan_id} 资源调度已持久化（{len(resources)} 项）")

    async def save_notifications(self, plan_id: str, notifications: list[dict]) -> None:
        """保存通知记录（事务）"""
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
        logger.info(f"预案 {plan_id} 通知记录已持久化（{len(notifications)} 条）")

    # ──────────────────────────────────────
    # 预案查询
    # ──────────────────────────────────────

    async def get_emergency_plan(self, plan_id: str) -> dict | None:
        """获取预案详情"""
        return await self._fetchrow("""
            SELECT plan_id, plan_name, risk_level, trigger_conditions, status,
                   session_id, summary, created_at, updated_at
            FROM emergency_plan WHERE plan_id = $1
        """, plan_id)

    async def get_plan_actions(self, plan_id: str) -> list[dict]:
        """获取预案措施列表"""
        return await self._fetch("""
            SELECT action_id, action_type, description, priority, responsible_dept,
                   deadline_minutes, status, created_at
            FROM emergency_action WHERE plan_id = $1
            ORDER BY priority ASC, created_at ASC, action_id ASC
        """, plan_id)

    async def get_plan_resources(self, plan_id: str) -> list[dict]:
        """获取预案资源调度列表"""
        return await self._fetch("""
            SELECT resource_type, resource_name, quantity, source_location,
                   target_location, eta_minutes, created_at
            FROM resource_allocation WHERE plan_id = $1
        """, plan_id)

    async def get_plan_notifications(self, plan_id: str) -> list[dict]:
        """获取预案通知列表"""
        return await self._fetch("""
            SELECT target, channel, content, status, sent_at, created_at
            FROM notification_record WHERE plan_id = $1
        """, plan_id)

    async def get_plans(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """获取预案列表"""
        return await self._fetch("""
            SELECT plan_id, plan_name, risk_level, status, session_id, summary, created_at
            FROM emergency_plan
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """, limit, offset)

    async def get_plan_count(self) -> int:
        """获取预案总数"""
        result = await self._fetchval("SELECT COUNT(*) FROM emergency_plan")
        return result or 0

    async def update_plan_status(self, plan_id: str, status: str) -> None:
        """更新预案状态"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE emergency_plan SET status = $1, updated_at = NOW() WHERE plan_id = $2
            """, status, plan_id)
        logger.info(f"预案 {plan_id} 状态已更新为 {status}")

    async def update_action_status(self, plan_id: str, action_id: str, status: str) -> None:
        """更新单条应急措施的执行状态"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE emergency_action
                SET status = $1
                WHERE plan_id = $2 AND action_id = $3
            """, status, plan_id, action_id)
        logger.debug(f"措施 {action_id}（预案 {plan_id}）状态更新为 {status}")

    async def get_plans_by_session(self, session_id: str) -> list[dict]:
        """根据会话ID获取相关预案"""
        return await self._fetch("""
            SELECT plan_id, plan_name, risk_level, status, created_at
            FROM emergency_plan WHERE session_id = $1
            ORDER BY created_at DESC
        """, session_id)

    # ──────────────────────────────────────
    # 会话历史查询
    # ──────────────────────────────────────

    async def get_sessions(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """获取会话列表"""
        return await self._fetch("""
            SELECT session_id, created_at, updated_at
            FROM emergency_plan
            GROUP BY session_id
            ORDER BY MAX(created_at) DESC
            LIMIT $1 OFFSET $2
        """, limit, offset)

    async def get_session_count(self) -> int:
        """获取会话总数"""
        result = await self._fetchval("SELECT COUNT(DISTINCT session_id) FROM emergency_plan")
        return result or 0


# 全局单例
_service: DatabaseService | None = None


def get_db_service() -> DatabaseService:
    global _service
    if _service is None:
        _service = DatabaseService()
    return _service
