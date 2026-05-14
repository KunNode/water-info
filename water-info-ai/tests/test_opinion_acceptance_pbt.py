"""Property-based test for opinion acceptance domain.

Feature: plan-human-review, Property 4: opinion validity

**Validates: Requirements 4.6, 4.7**

Property 4: For any string `opinion`, approve is accepted if and only if
`opinion.strip().length ∈ [1, 500]`; otherwise 422 + status stays draft + no audit record.

Hypothesis generates: pure whitespace, boundary lengths (0/1/500/501),
mixed leading/trailing whitespace, multi-byte characters.

This test requires a live PostgreSQL database with the plan tables bootstrapped.
It will be skipped if the database is not reachable.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import pytest

try:
    import asyncpg
except ImportError:
    asyncpg = None  # type: ignore[assignment]

from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from app.services.plan_review import PlanReviewService, Reviewer, ValidationFailedError


# ── Database connection helpers ───────────────────────────────────────────────


def _get_dsn_params() -> dict[str, Any]:
    return {
        "host": os.environ.get("PG_HOST", "localhost"),
        "port": int(os.environ.get("PG_PORT", "5432")),
        "database": os.environ.get("PG_DATABASE", "water_info"),
        "user": os.environ.get("PG_USER", "postgres"),
        "password": os.environ.get("PG_PASSWORD", "postgres"),
    }


def _can_connect() -> bool:
    """Check if we can connect to the test database."""
    if asyncpg is None:
        return False
    try:
        async def _check():
            conn = await asyncpg.connect(**_get_dsn_params(), timeout=5)
            await conn.close()
            return True
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_check())
        finally:
            loop.close()
    except Exception:
        return False


_DB_AVAILABLE = _can_connect()

pytestmark = pytest.mark.skipif(
    not _DB_AVAILABLE,
    reason="PostgreSQL not available (asyncpg not installed or DB unreachable)",
)


# ── Ensure tables exist ──────────────────────────────────────────────────────


async def _ensure_tables(conn: asyncpg.Connection) -> None:
    """Ensure all required tables and columns exist."""
    await conn.execute("""
        ALTER TABLE emergency_plan ADD COLUMN IF NOT EXISTS version INT NOT NULL DEFAULT 0
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS "user" (
            id BIGSERIAL PRIMARY KEY,
            username VARCHAR(255) NOT NULL DEFAULT ''
        )
    """)


# ── Hypothesis strategies ─────────────────────────────────────────────────────

# Characters safe for PostgreSQL (no null bytes, no surrogates)
_pg_safe_char = st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00")

# Multi-byte characters (CJK, emoji, etc.)
_multibyte_char = st.sampled_from(
    "你好世界防汛应急预案批准同意执行🌊🚨⚠️💧🏗️"
)


@st.composite
def opinion_st(draw) -> str:
    """Generate opinion strings covering the full domain:
    - Pure whitespace (strip → empty)
    - Boundary lengths: 0, 1, 500, 501
    - Mixed leading/trailing whitespace
    - Multi-byte characters
    """
    strategy_choice = draw(st.integers(min_value=0, max_value=6))

    if strategy_choice == 0:
        # Pure whitespace → strip length = 0
        return draw(st.text(alphabet=" \t\n\r", min_size=0, max_size=10))

    elif strategy_choice == 1:
        # Exactly 1 char after strip (boundary: minimum valid)
        core = draw(st.one_of(
            st.text(alphabet=_pg_safe_char, min_size=1, max_size=1),
            st.text(alphabet=_multibyte_char, min_size=1, max_size=1),
        ))
        prefix = draw(st.text(alphabet=" \t\n\r", min_size=0, max_size=3))
        suffix = draw(st.text(alphabet=" \t\n\r", min_size=0, max_size=3))
        return prefix + core + suffix

    elif strategy_choice == 2:
        # Exactly 500 chars after strip (boundary: maximum valid)
        core = draw(st.text(alphabet=_pg_safe_char, min_size=500, max_size=500))
        # Ensure strip doesn't reduce length
        assume(len(core.strip()) == 500)
        prefix = draw(st.text(alphabet=" \t", min_size=0, max_size=3))
        suffix = draw(st.text(alphabet=" \t", min_size=0, max_size=3))
        return prefix + core + suffix

    elif strategy_choice == 3:
        # Exactly 501 chars after strip (boundary: minimum invalid over-length)
        core = draw(st.text(alphabet=_pg_safe_char, min_size=501, max_size=501))
        assume(len(core.strip()) == 501)
        prefix = draw(st.text(alphabet=" \t", min_size=0, max_size=2))
        suffix = draw(st.text(alphabet=" \t", min_size=0, max_size=2))
        return prefix + core + suffix

    elif strategy_choice == 4:
        # Multi-byte characters (valid range)
        length = draw(st.integers(min_value=1, max_value=100))
        core = draw(st.text(alphabet=_multibyte_char, min_size=length, max_size=length))
        assume(1 <= len(core.strip()) <= 500)
        return core

    elif strategy_choice == 5:
        # General arbitrary text (may be valid or invalid)
        text = draw(st.text(alphabet=_pg_safe_char, min_size=0, max_size=600))
        return text

    else:
        # Empty string
        return ""


# ── Test infrastructure ───────────────────────────────────────────────────────

_loop = asyncio.new_event_loop()
_pool: asyncpg.Pool | None = None
_test_user_id: str | None = None


def setup_module():
    """Set up test database connection pool and ensure tables."""
    global _pool, _test_user_id
    if not _DB_AVAILABLE:
        return

    async def _setup():
        global _pool, _test_user_id
        _pool = await asyncpg.create_pool(**_get_dsn_params(), min_size=2, max_size=5, timeout=10)
        async with _pool.acquire() as conn:
            await _ensure_tables(conn)
            row = await conn.fetchrow('SELECT id FROM "user" LIMIT 1')
            if row:
                _test_user_id = str(row["id"])
            else:
                uid = await conn.fetchval(
                    'INSERT INTO "user" (username) VALUES ($1) RETURNING id',
                    "pbt_opinion_tester",
                )
                _test_user_id = str(uid)

    _loop.run_until_complete(_setup())


def teardown_module():
    """Close pool."""
    global _pool
    if _pool is None:
        return

    async def _teardown():
        global _pool
        await _pool.close()
        _pool = None

    _loop.run_until_complete(_teardown())
    _loop.close()


async def _create_fresh_draft_plan(conn: asyncpg.Connection) -> str:
    """Create a fresh draft plan with unique ID. Returns plan_id."""
    plan_id = f"pbt-opinion-{uuid.uuid4().hex[:12]}"
    await conn.execute(
        "INSERT INTO emergency_plan (plan_id, plan_name, summary, status, version) "
        "VALUES ($1, $2, $3, $4, $5)",
        plan_id, "PBT Opinion Test Plan", "Initial summary", "draft", 0,
    )
    return plan_id


async def _cleanup_plan(conn: asyncpg.Connection, plan_id: str) -> None:
    """Remove test plan and all related data (cascades)."""
    await conn.execute("DELETE FROM emergency_plan WHERE plan_id = $1", plan_id)


async def _get_plan_status_and_version(conn: asyncpg.Connection, plan_id: str) -> tuple[str, int]:
    """Get current status and version of a plan."""
    row = await conn.fetchrow(
        "SELECT status, version FROM emergency_plan WHERE plan_id = $1", plan_id
    )
    return row["status"], row["version"]


async def _count_audit_records(conn: asyncpg.Connection, plan_id: str) -> int:
    """Count audit records for a plan."""
    return await conn.fetchval(
        "SELECT COUNT(*) FROM plan_audit_record WHERE plan_id = $1", plan_id
    )


# ── Property test ─────────────────────────────────────────────────────────────


@given(opinion=opinion_st())
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_opinion_acceptance_domain(opinion):
    """Feature: plan-human-review, Property 4: opinion validity

    **Validates: Requirements 4.6, 4.7**

    For any string `opinion`, approve is accepted if and only if
    opinion.strip().length ∈ [1, 500]; otherwise 422 + status stays draft
    + no audit record created.
    """
    assert _pool is not None and _test_user_id is not None

    stripped = opinion.strip()
    should_accept = 1 <= len(stripped) <= 500

    reviewer = Reviewer(user_id=_test_user_id, username="pbt_opinion_tester")

    async def _run():
        service = PlanReviewService(_pool)

        # Create a fresh draft plan for each test case
        async with _pool.acquire() as conn:
            plan_id = await _create_fresh_draft_plan(conn)

        try:
            async with _pool.acquire() as conn:
                records_before = await _count_audit_records(conn, plan_id)

            if should_accept:
                # Should succeed
                result = await service.approve(
                    plan_id=plan_id,
                    version=0,
                    opinion=opinion,
                    reviewer=reviewer,
                )
                # Verify success
                assert result["status"] == "approved"
                assert result["version"] == 1

                async with _pool.acquire() as conn:
                    status, version = await _get_plan_status_and_version(conn, plan_id)
                    assert status == "approved", f"Expected approved, got {status}"
                    assert version == 1

                    # Exactly one audit record created
                    records_after = await _count_audit_records(conn, plan_id)
                    assert records_after == records_before + 1
            else:
                # Should be rejected with ValidationFailedError (maps to 422)
                with pytest.raises(ValidationFailedError) as exc_info:
                    await service.approve(
                        plan_id=plan_id,
                        version=0,
                        opinion=opinion,
                        reviewer=reviewer,
                    )

                assert exc_info.value.status_code == 422

                # Status stays draft, version unchanged, no audit record
                async with _pool.acquire() as conn:
                    status, version = await _get_plan_status_and_version(conn, plan_id)
                    assert status == "draft", f"Expected draft, got {status}"
                    assert version == 0, f"Expected version 0, got {version}"

                    records_after = await _count_audit_records(conn, plan_id)
                    assert records_after == records_before, (
                        f"No audit record should be created, but count changed "
                        f"from {records_before} to {records_after}"
                    )
        finally:
            async with _pool.acquire() as conn:
                await _cleanup_plan(conn, plan_id)

    _loop.run_until_complete(_run())
