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
