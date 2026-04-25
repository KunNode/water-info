"""PostgreSQL async database service for water data and plan persistence."""

from __future__ import annotations

import asyncio
import json
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

    @staticmethod
    def _json_or_none(value: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _decode_json_field(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

    @staticmethod
    def _vector_literal(values: list[float]) -> str:
        return "[" + ",".join(f"{value:.8f}" for value in values) + "]"

    def _normalize_kb_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(row)
        if "metadata" in normalized:
            normalized["metadata"] = self._decode_json_field(normalized["metadata"]) or {}
        if "heading_path" in normalized:
            heading_path = self._decode_json_field(normalized["heading_path"])
            normalized["heading_path"] = heading_path if isinstance(heading_path, list) else []
        return normalized

    # ── Stations ──────────────────────────────────────────────────────────────

    async def get_station_with_latest_data(self, limit: int = 20) -> list[dict]:
        """Return stations sorted by alarm priority; capped at `limit` rows."""
        return await self._fetch("""
            WITH latest_obs AS (
                SELECT DISTINCT ON (station_id, metric_type)
                    station_id, metric_type, value, observed_at
                FROM observation
                ORDER BY station_id, metric_type, observed_at DESC
            ),
            alarm_counts AS (
                SELECT station_id, COUNT(*) AS alarm_cnt
                FROM alarm WHERE status IN ('OPEN', 'ACK')
                GROUP BY station_id
            )
            SELECT
                s.id, s.code, s.name, s.type, s.river_basin, s.admin_region,
                s.lat, s.lon, s.status,
                wl.value  AS water_level,
                wl.observed_at AS water_level_time,
                rf.value  AS rainfall,
                rf.observed_at AS rainfall_time,
                fl.value  AS flow_rate,
                fl.observed_at AS flow_rate_time,
                COALESCE(ac.alarm_cnt, 0) AS alarm_cnt
            FROM station s
            LEFT JOIN latest_obs wl ON wl.station_id = s.id AND wl.metric_type = 'WATER_LEVEL'
            LEFT JOIN latest_obs rf ON rf.station_id = s.id AND rf.metric_type = 'RAINFALL'
            LEFT JOIN latest_obs fl ON fl.station_id = s.id AND fl.metric_type = 'FLOW'
            LEFT JOIN alarm_counts ac ON ac.station_id = s.id
            ORDER BY alarm_cnt DESC, s.code
            LIMIT $1
        """, limit)

    async def list_active_stations(self, limit: int = 100) -> list[dict]:
        """Return active stations for background risk scans."""
        return await self._fetch("""
            SELECT id, code, name
            FROM station
            WHERE UPPER(status) = 'ACTIVE'
            ORDER BY code
            LIMIT $1
        """, limit)

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

    async def get_active_alarms(self, station_id: str | None = None, limit: int = 15) -> list[dict]:
        if station_id:
            return await self._fetch("""
                SELECT a.id, a.station_id, s.name AS station_name, a.metric_type,
                       a.level, a.status, a.message, a.start_at, a.last_trigger_at
                FROM alarm a JOIN station s ON s.id = a.station_id
                WHERE a.status IN ('OPEN', 'ACK') AND a.station_id = $1
                ORDER BY a.level DESC, a.last_trigger_at DESC
                LIMIT $2
            """, station_id, limit)
        return await self._fetch("""
            SELECT a.id, a.station_id, s.name AS station_name, a.metric_type,
                   a.level, a.status, a.message, a.start_at, a.last_trigger_at
            FROM alarm a JOIN station s ON s.id = a.station_id
            WHERE a.status IN ('OPEN', 'ACK')
            ORDER BY a.level DESC, a.last_trigger_at DESC
            LIMIT $1
        """, limit)

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

    # ── Conversation tables DDL ───────────────────────────────────────────────

    async def ensure_conversation_tables(self) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Task 1: conversation_session with extended fields
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_session (
                    session_id  VARCHAR(128) PRIMARY KEY,
                    title       VARCHAR(255) NOT NULL DEFAULT '新会话',
                    user_id     VARCHAR(64) NOT NULL DEFAULT '',
                    username    VARCHAR(64) NOT NULL DEFAULT '',
                    status      VARCHAR(32) NOT NULL DEFAULT 'active',
                    last_message_at TIMESTAMPTZ,
                    last_message_preview TEXT NOT NULL DEFAULT '',
                    title_source VARCHAR(32) NOT NULL DEFAULT 'auto_first_query',
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            # Add columns if table already exists (migration)
            await conn.execute("""
                DO $$ BEGIN
                    ALTER TABLE conversation_session ADD COLUMN IF NOT EXISTS user_id VARCHAR(64) NOT NULL DEFAULT '';
                    ALTER TABLE conversation_session ADD COLUMN IF NOT EXISTS username VARCHAR(64) NOT NULL DEFAULT '';
                    ALTER TABLE conversation_session ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'active';
                    ALTER TABLE conversation_session ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMPTZ;
                    ALTER TABLE conversation_session ADD COLUMN IF NOT EXISTS last_message_preview TEXT NOT NULL DEFAULT '';
                    ALTER TABLE conversation_session ADD COLUMN IF NOT EXISTS title_source VARCHAR(32) NOT NULL DEFAULT 'auto_first_query';
                EXCEPTION WHEN others THEN NULL;
                END $$;
            """)
            # Index for user-based queries
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conv_session_user_updated
                    ON conversation_session(user_id, updated_at DESC)
            """)

            # Task 2: conversation_message with extended fields
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_message (
                    id          BIGSERIAL PRIMARY KEY,
                    session_id  VARCHAR(128) NOT NULL
                                    REFERENCES conversation_session(session_id) ON DELETE CASCADE,
                    role        VARCHAR(32) NOT NULL DEFAULT 'user',
                    content     TEXT NOT NULL DEFAULT '',
                    message_type VARCHAR(32) NOT NULL DEFAULT 'chat',
                    status      VARCHAR(32) NOT NULL DEFAULT 'completed',
                    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            # Add columns if table already exists (migration)
            await conn.execute("""
                DO $$ BEGIN
                    ALTER TABLE conversation_message ADD COLUMN IF NOT EXISTS message_type VARCHAR(32) NOT NULL DEFAULT 'chat';
                    ALTER TABLE conversation_message ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'completed';
                    ALTER TABLE conversation_message ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
                EXCEPTION WHEN others THEN NULL;
                END $$;
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conv_msg_session
                    ON conversation_message(session_id, created_at)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conv_msg_session_id
                    ON conversation_message(session_id, id)
            """)

            # Task 3: conversation_snapshot for business state recovery
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_snapshot (
                    session_id VARCHAR(128) PRIMARY KEY
                        REFERENCES conversation_session(session_id) ON DELETE CASCADE,
                    risk_level VARCHAR(32) NOT NULL DEFAULT 'none',
                    plan_info JSONB NOT NULL DEFAULT '{}'::jsonb,
                    agent_status_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
                    query_count INT NOT NULL DEFAULT 0,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            # Task 4: Memory system tables (placeholder)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_summary (
                    id          BIGSERIAL PRIMARY KEY,
                    session_id  VARCHAR(128) NOT NULL
                                    REFERENCES conversation_session(session_id) ON DELETE CASCADE,
                    summary     TEXT NOT NULL DEFAULT '',
                    start_turn  INT NOT NULL DEFAULT 0,
                    end_turn    INT NOT NULL DEFAULT 0,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conv_summary_session
                    ON conversation_summary(session_id, created_at DESC)
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_item (
                    id          BIGSERIAL PRIMARY KEY,
                    session_id  VARCHAR(128) NOT NULL
                                    REFERENCES conversation_session(session_id) ON DELETE CASCADE,
                    item_type   VARCHAR(32) NOT NULL DEFAULT 'fact',
                    content     TEXT NOT NULL DEFAULT '',
                    importance  FLOAT NOT NULL DEFAULT 0.5,
                    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_item_session
                    ON memory_item(session_id, item_type, created_at DESC)
            """)

    # ── Conversation write ────────────────────────────────────────────────────

    async def ensure_or_create_session(
        self,
        session_id: str,
        title: str = "",
        user_id: str = "",
        username: str = "",
        title_source: str = "auto_first_query",
    ) -> None:
        """Create or update a conversation session with user ownership."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO conversation_session (session_id, title, user_id, username, title_source)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (session_id) DO UPDATE SET updated_at = NOW()
            """, session_id, title or "新会话", user_id, username, title_source)

    async def save_conversation_message(
        self,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "chat",
        status: str = "completed",
        metadata: dict | None = None,
    ) -> int:
        """Save a message and update session's last_message fields. Returns message id."""
        import json
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            msg_id = await conn.fetchval("""
                INSERT INTO conversation_message (session_id, role, content, message_type, status, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
            """, session_id, role, content, message_type, status, json.dumps(metadata or {}))
            preview = (content[:100] + "…") if len(content) > 100 else content
            await conn.execute("""
                UPDATE conversation_session
                SET updated_at = NOW(),
                    last_message_at = NOW(),
                    last_message_preview = $2
                WHERE session_id = $1
            """, session_id, preview)
            return msg_id

    async def update_message_content(self, message_id: int, content: str, status: str = "completed") -> None:
        """Update an existing message's content and status (for streaming completion)."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE conversation_message
                SET content = $2, status = $3
                WHERE id = $1
            """, message_id, content, status)
            # Also update session's last_message_preview
            row = await conn.fetchrow(
                "SELECT session_id FROM conversation_message WHERE id = $1", message_id
            )
            if row:
                preview = (content[:100] + "…") if len(content) > 100 else content
                await conn.execute("""
                    UPDATE conversation_session
                    SET updated_at = NOW(), last_message_at = NOW(), last_message_preview = $2
                    WHERE session_id = $1
                """, row["session_id"], preview)

    async def update_session_title(self, session_id: str, title: str, title_source: str = "manual") -> None:
        """Update session title. If title_source is 'manual', future auto-updates are prevented."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE conversation_session
                SET title = $1, title_source = $3, updated_at = NOW()
                WHERE session_id = $2
            """, title, session_id, title_source)

    async def delete_conversation(self, session_id: str, user_id: str | None = None) -> bool:
        """Delete a conversation. If user_id is provided, only delete if owned by user."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if user_id:
                result = await conn.execute(
                    "DELETE FROM conversation_session WHERE session_id = $1 AND user_id = $2",
                    session_id, user_id
                )
            else:
                result = await conn.execute(
                    "DELETE FROM conversation_session WHERE session_id = $1", session_id
                )
            return result.split()[-1] != "0"

    # ── Snapshot write ────────────────────────────────────────────────────────

    async def save_conversation_snapshot(
        self,
        session_id: str,
        risk_level: str = "none",
        plan_info: dict | None = None,
        agent_status_summary: dict | None = None,
        query_count: int | None = None,
    ) -> None:
        """Upsert the conversation snapshot for business state recovery."""
        import json
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if query_count is None:
                # Auto-increment query_count
                await conn.execute("""
                    INSERT INTO conversation_snapshot (session_id, risk_level, plan_info, agent_status_summary, query_count, updated_at)
                    VALUES ($1, $2, $3, $4, 1, NOW())
                    ON CONFLICT (session_id) DO UPDATE SET
                        risk_level = EXCLUDED.risk_level,
                        plan_info = EXCLUDED.plan_info,
                        agent_status_summary = EXCLUDED.agent_status_summary,
                        query_count = conversation_snapshot.query_count + 1,
                        updated_at = NOW()
                """, session_id, risk_level, json.dumps(plan_info or {}), json.dumps(agent_status_summary or {}))
            else:
                await conn.execute("""
                    INSERT INTO conversation_snapshot (session_id, risk_level, plan_info, agent_status_summary, query_count, updated_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                    ON CONFLICT (session_id) DO UPDATE SET
                        risk_level = EXCLUDED.risk_level,
                        plan_info = EXCLUDED.plan_info,
                        agent_status_summary = EXCLUDED.agent_status_summary,
                        query_count = EXCLUDED.query_count,
                        updated_at = NOW()
                """, session_id, risk_level, json.dumps(plan_info or {}), json.dumps(agent_status_summary or {}), query_count)

    async def get_conversation_snapshot(self, session_id: str) -> dict | None:
        """Get the snapshot for a session."""
        return await self._fetchrow("""
            SELECT session_id, risk_level, plan_info, agent_status_summary, query_count, updated_at
            FROM conversation_snapshot WHERE session_id = $1
        """, session_id)

    # ── Memory system write (placeholder) ─────────────────────────────────────

    async def save_conversation_summary(
        self,
        session_id: str,
        summary: str,
        start_turn: int,
        end_turn: int,
    ) -> int:
        """Save a conversation summary for memory system."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval("""
                INSERT INTO conversation_summary (session_id, summary, start_turn, end_turn)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, session_id, summary, start_turn, end_turn)

    async def save_memory_item(
        self,
        session_id: str,
        item_type: str,
        content: str,
        importance: float = 0.5,
        metadata: dict | None = None,
    ) -> int:
        """Save a memory item (fact, decision, todo, etc.)."""
        import json
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval("""
                INSERT INTO memory_item (session_id, item_type, content, importance, metadata)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """, session_id, item_type, content, importance, json.dumps(metadata or {}))

    # ── Conversation read ─────────────────────────────────────────────────────

    async def get_conversation_messages(
        self,
        session_id: str,
        limit: int = 40,
        before_id: int | None = None,
    ) -> list[dict]:
        """Return messages for a session with cursor-based pagination.
        
        If before_id is provided, returns messages with id < before_id (for loading history).
        Messages are returned oldest-first.
        """
        if before_id is not None:
            return await self._fetch("""
                SELECT id, role, content, message_type, status, metadata, created_at FROM (
                    SELECT id, role, content, message_type, status, metadata, created_at
                    FROM conversation_message
                    WHERE session_id = $1 AND id < $3
                    ORDER BY id DESC
                    LIMIT $2
                ) sub
                ORDER BY id ASC
            """, session_id, limit, before_id)
        return await self._fetch("""
            SELECT id, role, content, message_type, status, metadata, created_at FROM (
                SELECT id, role, content, message_type, status, metadata, created_at
                FROM conversation_message
                WHERE session_id = $1
                ORDER BY id DESC
                LIMIT $2
            ) sub
            ORDER BY id ASC
        """, session_id, limit)

    async def get_session_by_id(self, session_id: str, user_id: str | None = None) -> dict | None:
        """Get a session by ID, optionally filtering by user_id for access control."""
        if user_id:
            return await self._fetchrow("""
                SELECT session_id, title, user_id, username, status, last_message_at,
                       last_message_preview, title_source, created_at, updated_at
                FROM conversation_session
                WHERE session_id = $1 AND user_id = $2
            """, session_id, user_id)
        return await self._fetchrow("""
            SELECT session_id, title, user_id, username, status, last_message_at,
                   last_message_preview, title_source, created_at, updated_at
            FROM conversation_session
            WHERE session_id = $1
        """, session_id)

    async def list_conversations(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: str | None = None,
    ) -> list[dict]:
        """List conversations, optionally filtered by user_id."""
        if user_id:
            return await self._fetch("""
                SELECT
                    s.session_id, s.title, s.user_id, s.username, s.status,
                    s.last_message_at, s.last_message_preview, s.title_source,
                    s.created_at, s.updated_at,
                    COUNT(m.id) AS message_count,
                    s.last_message_preview AS last_message
                FROM conversation_session s
                LEFT JOIN conversation_message m ON m.session_id = s.session_id
                WHERE s.user_id = $3 AND s.status != 'deleted'
                GROUP BY s.session_id
                ORDER BY s.updated_at DESC
                LIMIT $1 OFFSET $2
            """, limit, offset, user_id)
        return await self._fetch("""
            SELECT
                s.session_id, s.title, s.user_id, s.username, s.status,
                s.last_message_at, s.last_message_preview, s.title_source,
                s.created_at, s.updated_at,
                COUNT(m.id) AS message_count,
                s.last_message_preview AS last_message
            FROM conversation_session s
            LEFT JOIN conversation_message m ON m.session_id = s.session_id
            WHERE s.status != 'deleted'
            GROUP BY s.session_id
            ORDER BY s.updated_at DESC
            LIMIT $1 OFFSET $2
        """, limit, offset)

    async def get_conversation_count(self, user_id: str | None = None) -> int:
        if user_id:
            return (await self._fetchval(
                "SELECT COUNT(*) FROM conversation_session WHERE user_id = $1 AND status != 'deleted'",
                user_id
            )) or 0
        return (await self._fetchval(
            "SELECT COUNT(*) FROM conversation_session WHERE status != 'deleted'"
        )) or 0

    async def check_session_ownership(self, session_id: str, user_id: str) -> bool:
        """Check if a session belongs to a user."""
        count = await self._fetchval(
            "SELECT COUNT(*) FROM conversation_session WHERE session_id = $1 AND user_id = $2",
            session_id, user_id
        )
        return (count or 0) > 0

    # ── Plan tables DDL ───────────────────────────────────────────────────────

    async def ensure_plan_tables(self) -> None:
        await self.ensure_conversation_tables()
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

    # ── Knowledge base tables DDL ────────────────────────────────────────────

    async def ensure_kb_tables(self) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            embedding_dim = int(self._settings.embedding_dim or 1024)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS kb_document (
                    id              VARCHAR(64) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                    title           VARCHAR(255) NOT NULL,
                    source_type     VARCHAR(32) NOT NULL DEFAULT 'upload',
                    source_uri      TEXT NOT NULL DEFAULT '',
                    mime            VARCHAR(128) NOT NULL DEFAULT 'text/plain',
                    lang            VARCHAR(32) NOT NULL DEFAULT 'zh-CN',
                    version         INT NOT NULL DEFAULT 1,
                    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
                    content_hash    VARCHAR(64) NOT NULL DEFAULT '',
                    raw_text        TEXT NOT NULL DEFAULT '',
                    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
                    chunk_count     INT NOT NULL DEFAULT 0,
                    file_size       BIGINT NOT NULL DEFAULT 0,
                    embedding_model VARCHAR(128) NOT NULL DEFAULT '',
                    created_by      VARCHAR(64) NOT NULL DEFAULT '',
                    last_indexed_at TIMESTAMPTZ,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    deleted         BOOLEAN NOT NULL DEFAULT FALSE
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS kb_chunk (
                    id          VARCHAR(64) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                    document_id VARCHAR(64) NOT NULL REFERENCES kb_document(id) ON DELETE CASCADE,
                    chunk_index INT NOT NULL,
                    content     TEXT NOT NULL,
                    token_count INT NOT NULL DEFAULT 0,
                    heading_path JSONB NOT NULL DEFAULT '[]'::jsonb,
                    search_text TEXT NOT NULL DEFAULT '',
                    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (document_id, chunk_index)
                )
            """)
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS kb_embedding (
                    chunk_id     VARCHAR(64) PRIMARY KEY REFERENCES kb_chunk(id) ON DELETE CASCADE,
                    model        VARCHAR(128) NOT NULL DEFAULT '',
                    dimensions   INT NOT NULL DEFAULT 0,
                    embedding    vector({embedding_dim}) NOT NULL,
                    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS kb_ingest_job (
                    id          VARCHAR(64) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                    document_id VARCHAR(64) NOT NULL REFERENCES kb_document(id) ON DELETE CASCADE,
                    status      VARCHAR(32) NOT NULL DEFAULT 'pending',
                    error       TEXT,
                    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    finished_at TIMESTAMPTZ
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kb_document_status_deleted
                    ON kb_document(status, deleted, updated_at DESC)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kb_document_hash
                    ON kb_document(content_hash)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kb_chunk_document
                    ON kb_chunk(document_id, chunk_index)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kb_chunk_search
                    ON kb_chunk USING gin (to_tsvector('simple', search_text))
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kb_embedding_model_dims
                    ON kb_embedding(model, dimensions)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_kb_embedding_hnsw
                    ON kb_embedding USING hnsw (embedding vector_cosine_ops)
            """)

    async def upsert_kb_document_shell(
        self,
        *,
        title: str,
        source_type: str,
        source_uri: str,
        mime: str,
        content_hash: str,
        file_size: int,
        created_by: str,
    ) -> dict[str, Any]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                """
                SELECT id, version
                FROM kb_document
                WHERE content_hash = $1 AND deleted = FALSE
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                content_hash,
            )
            if existing:
                row = await conn.fetchrow(
                    """
                    UPDATE kb_document
                    SET title = $2,
                        source_type = $3,
                        source_uri = $4,
                        mime = $5,
                        file_size = $6,
                        created_by = $7,
                        status = 'pending',
                        version = version + 1,
                        deleted = FALSE,
                        updated_at = NOW()
                    WHERE id = $1
                    RETURNING id, version
                    """,
                    existing["id"],
                    title,
                    source_type,
                    source_uri,
                    mime,
                    file_size,
                    created_by,
                )
                return dict(row) if row else {"id": existing["id"], "version": existing["version"]}

            row = await conn.fetchrow(
                """
                INSERT INTO kb_document (
                    title, source_type, source_uri, mime, content_hash, file_size, created_by, status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')
                RETURNING id, version
                """,
                title,
                source_type,
                source_uri,
                mime,
                content_hash,
                file_size,
                created_by,
            )
            return dict(row) if row else {}

    async def create_kb_ingest_job(self, document_id: str) -> str:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            return str(
                await conn.fetchval(
                    """
                    INSERT INTO kb_ingest_job (document_id, status)
                    VALUES ($1, 'pending')
                    RETURNING id
                    """,
                    document_id,
                )
            )

    async def finish_kb_ingest_job(self, job_id: str, status: str, *, error: str | None = None) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE kb_ingest_job
                SET status = $2, error = $3, finished_at = NOW()
                WHERE id = $1
                """,
                job_id,
                status,
                error,
            )

    async def update_kb_document_status(
        self,
        document_id: str,
        status: str,
        *,
        raw_text: str | None = None,
        metadata: dict | None = None,
        embedding_model: str | None = None,
        chunk_count: int | None = None,
        mark_indexed: bool = False,
    ) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE kb_document
                SET status = $2,
                    raw_text = COALESCE($3, raw_text),
                    metadata = COALESCE($4::jsonb, metadata),
                    embedding_model = COALESCE($5, embedding_model),
                    chunk_count = COALESCE($6, chunk_count),
                    last_indexed_at = CASE WHEN $7 THEN NOW() ELSE last_indexed_at END,
                    updated_at = NOW()
                WHERE id = $1
                """,
                document_id,
                status,
                raw_text,
                self._json_or_none(metadata),
                embedding_model,
                chunk_count,
                mark_indexed,
            )

    async def replace_kb_document_chunks(
        self,
        *,
        document_id: str,
        title: str,
        source_uri: str,
        mime: str,
        raw_text: str,
        metadata: dict,
        chunk_candidates: list[Any],
        embedding_model: str,
        embeddings: list[list[float]] | None,
    ) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM kb_chunk WHERE document_id = $1", document_id)
                await conn.execute(
                    """
                    UPDATE kb_document
                    SET title = $2,
                        source_uri = $3,
                        mime = $4,
                        raw_text = $5,
                        metadata = $6::jsonb,
                        chunk_count = $7,
                        embedding_model = $8,
                        status = 'ready',
                        last_indexed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    document_id,
                    title,
                    source_uri,
                    mime,
                    raw_text,
                    self._json_or_none(metadata) or "{}",
                    len(chunk_candidates),
                    embedding_model,
                )
                for candidate in chunk_candidates:
                    chunk_id = await conn.fetchval(
                        """
                        INSERT INTO kb_chunk (
                            document_id, chunk_index, content, token_count, heading_path, search_text, metadata
                        )
                        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7::jsonb)
                        RETURNING id
                        """,
                        document_id,
                        candidate.chunk_index,
                        candidate.content,
                        candidate.token_count,
                        self._json_or_none(candidate.heading_path) or "[]",
                        candidate.search_text,
                        self._json_or_none(candidate.metadata) or "{}",
                    )
                    if embeddings and candidate.chunk_index < len(embeddings) and embeddings[candidate.chunk_index]:
                        vector = self._vector_literal(embeddings[candidate.chunk_index])
                        await conn.execute(
                            """
                            INSERT INTO kb_embedding (chunk_id, model, dimensions, embedding)
                            VALUES ($1, $2, $3, $4::vector)
                            """,
                            chunk_id,
                            embedding_model,
                            len(embeddings[candidate.chunk_index]),
                            vector,
                        )

    async def list_kb_documents(
        self,
        *,
        status: str | None = None,
        source_type: str | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        rows = await self._fetch(
            """
            SELECT
                d.id, d.title, d.source_type, d.source_uri, d.mime, d.lang, d.version, d.status,
                d.chunk_count, d.file_size, d.embedding_model, d.created_by, d.created_at, d.updated_at, d.last_indexed_at,
                d.metadata,
                (
                    SELECT j.status
                    FROM kb_ingest_job j
                    WHERE j.document_id = d.id
                    ORDER BY j.started_at DESC
                    LIMIT 1
                ) AS latest_job_status,
                (
                    SELECT COALESCE(j.error, '')
                    FROM kb_ingest_job j
                    WHERE j.document_id = d.id
                    ORDER BY j.started_at DESC
                    LIMIT 1
                ) AS latest_error
            FROM kb_document d
            WHERE d.deleted = FALSE
              AND ($1::text IS NULL OR d.status = $1)
              AND ($2::text IS NULL OR d.source_type = $2)
              AND ($3::text IS NULL OR d.title ILIKE '%' || $3 || '%' OR d.source_uri ILIKE '%' || $3 || '%')
            ORDER BY d.updated_at DESC
            LIMIT $4 OFFSET $5
            """,
            status,
            source_type,
            q,
            limit,
            offset,
        )
        return [self._normalize_kb_row(row) for row in rows]

    async def get_kb_document(self, document_id: str) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT
                d.id, d.title, d.source_type, d.source_uri, d.mime, d.lang, d.version, d.status,
                d.chunk_count, d.file_size, d.embedding_model, d.created_by, d.created_at, d.updated_at,
                d.last_indexed_at, d.raw_text, d.metadata,
                (
                    SELECT j.status
                    FROM kb_ingest_job j
                    WHERE j.document_id = d.id
                    ORDER BY j.started_at DESC
                    LIMIT 1
                ) AS latest_job_status,
                (
                    SELECT COALESCE(j.error, '')
                    FROM kb_ingest_job j
                    WHERE j.document_id = d.id
                    ORDER BY j.started_at DESC
                    LIMIT 1
                ) AS latest_error
            FROM kb_document d
            WHERE d.id = $1 AND d.deleted = FALSE
            """,
            document_id,
        )
        return self._normalize_kb_row(row) if row else None

    async def soft_delete_kb_document(self, document_id: str) -> bool:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("SELECT id FROM kb_document WHERE id = $1 AND deleted = FALSE", document_id)
                if not row:
                    return False
                await conn.execute("DELETE FROM kb_chunk WHERE document_id = $1", document_id)
                await conn.execute(
                    """
                    UPDATE kb_document
                    SET deleted = TRUE, status = 'deleted', chunk_count = 0, updated_at = NOW()
                    WHERE id = $1
                    """,
                    document_id,
                )
                return True

    async def vector_search_kb(
        self,
        embedding: list[float],
        *,
        top_n: int,
        source_types: list[str] | None,
        model: str,
    ) -> list[dict[str, Any]]:
        vector = self._vector_literal(embedding)
        rows = await self._fetch(
            """
            SELECT
                c.id AS chunk_id,
                c.document_id,
                d.title AS document_title,
                d.source_uri,
                c.content,
                c.heading_path,
                c.metadata,
                (1 - (e.embedding <=> $1::vector)) AS vector_score
            FROM kb_embedding e
            JOIN kb_chunk c ON c.id = e.chunk_id
            JOIN kb_document d ON d.id = c.document_id
            WHERE d.deleted = FALSE
              AND d.status = 'ready'
              AND e.model = $2
              AND ($3::text[] IS NULL OR d.source_type = ANY($3))
            ORDER BY e.embedding <=> $1::vector
            LIMIT $4
            """,
            vector,
            model,
            source_types,
            top_n,
        )
        normalized = []
        for row in rows:
            item = self._normalize_kb_row(row)
            item["score"] = item.get("vector_score")
            normalized.append(item)
        return normalized

    async def keyword_search_kb(
        self,
        tokenized_query: str,
        *,
        top_n: int,
        source_types: list[str] | None,
    ) -> list[dict[str, Any]]:
        rows = await self._fetch(
            """
            SELECT
                c.id AS chunk_id,
                c.document_id,
                d.title AS document_title,
                d.source_uri,
                c.content,
                c.heading_path,
                c.metadata,
                ts_rank_cd(to_tsvector('simple', c.search_text), plainto_tsquery('simple', $1)) AS keyword_score
            FROM kb_chunk c
            JOIN kb_document d ON d.id = c.document_id
            WHERE d.deleted = FALSE
              AND d.status = 'ready'
              AND ($2::text[] IS NULL OR d.source_type = ANY($2))
              AND to_tsvector('simple', c.search_text) @@ plainto_tsquery('simple', $1)
            ORDER BY keyword_score DESC
            LIMIT $3
            """,
            tokenized_query,
            source_types,
            top_n,
        )
        normalized = []
        for row in rows:
            item = self._normalize_kb_row(row)
            item["score"] = item.get("keyword_score")
            normalized.append(item)
        return normalized

    async def get_kb_stats(self) -> dict[str, Any]:
        document_count = int(
            (await self._fetchval("SELECT COUNT(*) FROM kb_document WHERE deleted = FALSE")) or 0
        )
        ready_document_count = int(
            (await self._fetchval("SELECT COUNT(*) FROM kb_document WHERE deleted = FALSE AND status = 'ready'")) or 0
        )
        chunk_count = int((await self._fetchval("SELECT COUNT(*) FROM kb_chunk")) or 0)
        job_success_rate = float(
            (
                await self._fetchval(
                    """
                    SELECT COALESCE(
                        AVG(CASE WHEN status = 'completed' THEN 1.0 ELSE 0.0 END),
                        0
                    )
                    FROM (
                        SELECT status
                        FROM kb_ingest_job
                        ORDER BY started_at DESC
                        LIMIT 20
                    ) recent
                    """
                )
            )
            or 0.0
        )
        rows = await self._fetch(
            """
            SELECT embedding_model, COUNT(*) AS count
            FROM kb_document
            WHERE deleted = FALSE AND status = 'ready' AND embedding_model <> ''
            GROUP BY embedding_model
            """
        )
        model_distribution = {
            str(row["embedding_model"]): int(row["count"])
            for row in rows
            if row.get("embedding_model")
        }
        return {
            "document_count": document_count,
            "ready_document_count": ready_document_count,
            "chunk_count": chunk_count,
            "job_success_rate": round(job_success_rate, 4),
            "model_distribution": model_distribution,
        }

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
