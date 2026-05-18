"""HITL pending-approvals DAO with CAS resolve.

Uses the existing asyncpg pool from ``app.database.get_db_service()``.
Table creation is idempotent via ``IF NOT EXISTS``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS pending_approvals (
    approval_id   TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL,
    agent_run_id  TEXT NOT NULL DEFAULT '',
    approval_type TEXT NOT NULL,
    payload_json  JSONB NOT NULL DEFAULT '{}',
    status        TEXT NOT NULL DEFAULT 'pending',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at   TIMESTAMPTZ,
    resolved_by   TEXT,
    resolution    TEXT,
    INDEX idx_pending_approvals_session (session_id),
    INDEX idx_pending_approvals_status  (status)
);
"""


@dataclass
class PendingApprovalRow:
    approval_id: str
    session_id: str
    agent_run_id: str = ""
    approval_type: str = ""
    payload_json: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    created_at: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution: str | None = None


class ApprovalsDAO:
    """Thin async DAO over ``pending_approvals`` table."""

    def __init__(self, db_service: Any) -> None:
        self._db = db_service

    async def ensure_table(self) -> None:
        pool = await self._db._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(_DDL)

    async def insert_pending(self, row: PendingApprovalRow) -> None:
        pool = await self._db._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO pending_approvals
                    (approval_id, session_id, agent_run_id, approval_type,
                     payload_json, status, created_at)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                """,
                row.approval_id,
                row.session_id,
                row.agent_run_id,
                row.approval_type,
                json.dumps(row.payload_json, ensure_ascii=False),
                row.status,
                row.created_at or datetime.now(UTC),
            )

    async def get(self, approval_id: str) -> PendingApprovalRow | None:
        pool = await self._db._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM pending_approvals WHERE approval_id = $1",
                approval_id,
            )
        if row is None:
            return None
        return PendingApprovalRow(
            approval_id=row["approval_id"],
            session_id=row["session_id"],
            agent_run_id=row["agent_run_id"],
            approval_type=row["approval_type"],
            payload_json=json.loads(row["payload_json"]) if row["payload_json"] else {},
            status=row["status"],
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
            resolved_by=row["resolved_by"],
            resolution=row["resolution"],
        )

    async def cas_resolve(
        self,
        approval_id: str,
        new_status: str,
        resolution: str,
        resolved_by: str = "",
    ) -> bool:
        """Compare-and-set: resolve only if current status is 'pending'.

        Returns True if the row was updated, False if already resolved.
        """
        pool = await self._db._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE pending_approvals
                SET status = $1, resolution = $2, resolved_by = $3, resolved_at = now()
                WHERE approval_id = $4 AND status = 'pending'
                """,
                new_status,
                resolution,
                resolved_by,
                approval_id,
            )
        return result == "UPDATE 1"


_dao: ApprovalsDAO | None = None


async def get_approvals_dao() -> ApprovalsDAO:
    global _dao
    if _dao is None:
        from app.database import get_db_service
        _dao = ApprovalsDAO(get_db_service())
        await _dao.ensure_table()
    return _dao
