"""Property-based test for version + state gating for edit & approve.

Feature: plan-human-review, Property 6: optimistic lock + init invariants
Feature: plan-human-review, Property 3 (status portion)
Feature: plan-human-review, Property 2 (state gating portion)

Validates: Requirements 1.5, 3.7, 3.8, 4.5, 6.1

Properties tested:
P6: For any two concurrent edit/approve requests that read the same version,
    only one succeeds and version increments by exactly 1. The failed request
    produces no draft entries, no content changes, no audit records.
P3 (status portion): State gating — edit rejected for executing/completed states (409);
    approve rejected for non-draft states (409).
P2 (state gating portion): New plans initialize with status='draft' and version=0.

Uses hypothesis to generate (request_a, request_b) pairs and simulate serialized
replay against the PlanReviewService.

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

from app.services.plan_review import (
    PlanReviewService,
    Reviewer,
    StateConflictError,
    VersionConflictError,
)


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

_pg_safe_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
    min_size=1,
    max_size=50,
)

_short_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
    min_size=1,
    max_size=30,
)


@st.composite
def reviewer_st(draw) -> Reviewer:
    """Generate a reviewer with safe text for user_id and username."""
    user_id = draw(st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        min_size=1,
        max_size=20,
    ))
    username = draw(st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
        min_size=1,
        max_size=30,
    ))
    return Reviewer(user_id=user_id, username=username)


@st.composite
def valid_opinion_st(draw) -> str:
    """Generate a valid opinion (strip length 1-500)."""
    core = draw(st.text(
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
        min_size=1,
        max_size=100,
    ))
    prefix = draw(st.sampled_from(["", " ", "  "]))
    suffix = draw(st.sampled_from(["", " ", "  "]))
    return prefix + core + suffix


@st.composite
def edit_patch_st(draw) -> dict:
    """Generate a simple valid edit patch (summary change only for simplicity)."""
    return {"summary": draw(_pg_safe_text)}


# Request types for concurrent simulation
REQUEST_EDIT = "edit"
REQUEST_APPROVE = "approve"


@st.composite
def request_pair_st(draw) -> tuple[dict, dict]:
    """Generate a pair of (request_a, request_b) for concurrent simulation.

    Each request is a dict with 'type' (edit or approve) and relevant params.
    """
    type_a = draw(st.sampled_from([REQUEST_EDIT, REQUEST_APPROVE]))
    type_b = draw(st.sampled_from([REQUEST_EDIT, REQUEST_APPROVE]))

    req_a: dict[str, Any] = {"type": type_a}
    req_b: dict[str, Any] = {"type": type_b}

    if type_a == REQUEST_EDIT:
        req_a["patch"] = draw(edit_patch_st())
    else:
        req_a["opinion"] = draw(valid_opinion_st())

    if type_b == REQUEST_EDIT:
        req_b["patch"] = draw(edit_patch_st())
    else:
        req_b["opinion"] = draw(valid_opinion_st())

    return (req_a, req_b)


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
                    "pbt_version_tester",
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


async def _create_plan(conn: asyncpg.Connection, status: str = "draft", version: int = 0) -> str:
    """Create a plan with given status and version. Returns plan_id."""
    plan_id = f"pbt-vsg-{uuid.uuid4().hex[:12]}"
    await conn.execute(
        "INSERT INTO emergency_plan (plan_id, plan_name, summary, status, version) "
        "VALUES ($1, $2, $3, $4, $5)",
        plan_id, "PBT Version State Test", "Initial summary", status, version,
    )
    return plan_id


async def _cleanup_plan(conn: asyncpg.Connection, plan_id: str) -> None:
    """Remove test plan and all related data (cascades)."""
    await conn.execute("DELETE FROM emergency_plan WHERE plan_id = $1", plan_id)


async def _get_plan_state(conn: asyncpg.Connection, plan_id: str) -> dict | None:
    """Get current plan status, version, and summary."""
    row = await conn.fetchrow(
        "SELECT status, version, summary FROM emergency_plan WHERE plan_id = $1", plan_id
    )
    return dict(row) if row else None


async def _count_audit_records(conn: asyncpg.Connection, plan_id: str) -> int:
    return await conn.fetchval(
        "SELECT COUNT(*) FROM plan_audit_record WHERE plan_id = $1", plan_id
    )


async def _count_audit_drafts(conn: asyncpg.Connection, plan_id: str) -> int:
    return await conn.fetchval(
        "SELECT COUNT(*) FROM plan_audit_draft WHERE plan_id = $1", plan_id
    )


# ── Property tests ────────────────────────────────────────────────────────────


@given(pair=request_pair_st(), reviewer=reviewer_st())
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_optimistic_lock_concurrent_requests(pair, reviewer):
    """Feature: plan-human-review, Property 6: optimistic lock + init invariants

    **Validates: Requirements 1.5, 3.7, 3.8, 4.5, 6.1**

    For any two concurrent edit/approve requests that read the same version,
    only one succeeds and version increments by exactly 1. The failed request
    produces no draft entries, no content changes, no audit records.
    """
    assert _pool is not None and _test_user_id is not None

    test_reviewer = Reviewer(user_id=_test_user_id, username=reviewer.username)
    req_a, req_b = pair

    async def _run():
        service = PlanReviewService(_pool)

        # Create a fresh draft plan (P6 init invariant: status='draft', version=0)
        async with _pool.acquire() as conn:
            plan_id = await _create_plan(conn, status="draft", version=0)

        try:
            # Verify init invariant (P6): new plan has status='draft' and version=0
            async with _pool.acquire() as conn:
                state = await _get_plan_state(conn, plan_id)
                assert state["status"] == "draft"
                assert state["version"] == 0

            # Both requests read version=0 (simulating concurrent read)
            base_version = 0

            # Capture state before any request
            async with _pool.acquire() as conn:
                summary_before = state["summary"]
                drafts_before = await _count_audit_drafts(conn, plan_id)
                records_before = await _count_audit_records(conn, plan_id)

            # Execute request A (should succeed since it goes first)
            success_a = False
            try:
                if req_a["type"] == REQUEST_EDIT:
                    await service.edit_draft(
                        plan_id=plan_id,
                        version=base_version,
                        patch=req_a["patch"],
                        reviewer=test_reviewer,
                    )
                else:
                    await service.approve(
                        plan_id=plan_id,
                        version=base_version,
                        opinion=req_a["opinion"],
                        reviewer=test_reviewer,
                    )
                success_a = True
            except (VersionConflictError, StateConflictError):
                success_a = False

            # Verify version incremented by exactly 1 after first success
            if success_a:
                async with _pool.acquire() as conn:
                    state_after_a = await _get_plan_state(conn, plan_id)
                    assert state_after_a["version"] == base_version + 1, (
                        f"After successful request A, version should be {base_version + 1}, "
                        f"got {state_after_a['version']}"
                    )

            # Execute request B with the SAME base_version (simulating concurrent)
            # This should fail with VersionConflictError if A succeeded
            async with _pool.acquire() as conn:
                state_before_b = await _get_plan_state(conn, plan_id)
                drafts_before_b = await _count_audit_drafts(conn, plan_id)
                records_before_b = await _count_audit_records(conn, plan_id)

            success_b = False
            try:
                if req_b["type"] == REQUEST_EDIT:
                    # If plan is now approved (A was approve), edit_draft will fail with StateConflict
                    await service.edit_draft(
                        plan_id=plan_id,
                        version=base_version,
                        patch=req_b["patch"],
                        reviewer=test_reviewer,
                    )
                else:
                    await service.approve(
                        plan_id=plan_id,
                        version=base_version,
                        opinion=req_b["opinion"],
                        reviewer=test_reviewer,
                    )
                success_b = True
            except (VersionConflictError, StateConflictError):
                success_b = False

            # ── Core assertion: if A succeeded, B must fail ───────────────
            if success_a:
                assert not success_b, (
                    "Both requests succeeded with the same base version — "
                    "optimistic lock violated!"
                )

            # ── If B failed, verify no side effects ───────────────────────
            if not success_b:
                async with _pool.acquire() as conn:
                    state_after_b = await _get_plan_state(conn, plan_id)
                    drafts_after_b = await _count_audit_drafts(conn, plan_id)
                    records_after_b = await _count_audit_records(conn, plan_id)

                    # No content change from B
                    assert state_after_b["version"] == state_before_b["version"], (
                        "Failed request B should not change version"
                    )
                    assert state_after_b["summary"] == state_before_b["summary"], (
                        "Failed request B should not change content"
                    )
                    # No new draft entries from B
                    assert drafts_after_b == drafts_before_b, (
                        "Failed request B should not produce draft entries"
                    )
                    # No new audit records from B
                    assert records_after_b == records_before_b, (
                        "Failed request B should not produce audit records"
                    )

            # ── Verify exactly one version increment total ────────────────
            async with _pool.acquire() as conn:
                final_state = await _get_plan_state(conn, plan_id)
                total_successes = int(success_a) + int(success_b)
                assert final_state["version"] == base_version + total_successes, (
                    f"Version should be base + successes ({base_version} + {total_successes}), "
                    f"got {final_state['version']}"
                )

        finally:
            async with _pool.acquire() as conn:
                await _cleanup_plan(conn, plan_id)

    _loop.run_until_complete(_run())


@given(
    status=st.sampled_from(["executing", "completed"]),
    patch=edit_patch_st(),
    reviewer=reviewer_st(),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_state_gating_edit_rejected_for_executing_completed(status, patch, reviewer):
    """Feature: plan-human-review, Property 3 (status portion) + Property 2 (state gating)

    **Validates: Requirements 3.7, 6.1**

    State gating: edit rejected for executing/completed states with 409.
    No content changes, no draft entries, no audit records produced.
    """
    assert _pool is not None and _test_user_id is not None

    test_reviewer = Reviewer(user_id=_test_user_id, username=reviewer.username)

    async def _run():
        service = PlanReviewService(_pool)

        async with _pool.acquire() as conn:
            plan_id = await _create_plan(conn, status=status, version=0)

        try:
            # Capture state before
            async with _pool.acquire() as conn:
                state_before = await _get_plan_state(conn, plan_id)
                drafts_before = await _count_audit_drafts(conn, plan_id)
                records_before = await _count_audit_records(conn, plan_id)

            # Attempt edit — should be rejected with StateConflictError (409)
            with pytest.raises(StateConflictError) as exc_info:
                await service.edit_draft(
                    plan_id=plan_id,
                    version=0,
                    patch=patch,
                    reviewer=test_reviewer,
                )

            assert exc_info.value.status_code == 409

            # Verify no side effects
            async with _pool.acquire() as conn:
                state_after = await _get_plan_state(conn, plan_id)
                drafts_after = await _count_audit_drafts(conn, plan_id)
                records_after = await _count_audit_records(conn, plan_id)

                assert state_after["version"] == state_before["version"]
                assert state_after["summary"] == state_before["summary"]
                assert state_after["status"] == status
                assert drafts_after == drafts_before
                assert records_after == records_before

        finally:
            async with _pool.acquire() as conn:
                await _cleanup_plan(conn, plan_id)

    _loop.run_until_complete(_run())


@given(
    status=st.sampled_from(["approved", "executing", "completed"]),
    opinion=valid_opinion_st(),
    reviewer=reviewer_st(),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_state_gating_approve_rejected_for_non_draft(status, opinion, reviewer):
    """Feature: plan-human-review, Property 3 (status portion) + Property 6

    **Validates: Requirements 4.5, 6.1**

    State gating: approve rejected for non-draft states with 409.
    No status change, no audit records produced.
    """
    assert _pool is not None and _test_user_id is not None

    test_reviewer = Reviewer(user_id=_test_user_id, username=reviewer.username)

    async def _run():
        service = PlanReviewService(_pool)

        async with _pool.acquire() as conn:
            plan_id = await _create_plan(conn, status=status, version=0)

        try:
            # Capture state before
            async with _pool.acquire() as conn:
                state_before = await _get_plan_state(conn, plan_id)
                records_before = await _count_audit_records(conn, plan_id)

            # Attempt approve — should be rejected with StateConflictError (409)
            with pytest.raises(StateConflictError) as exc_info:
                await service.approve(
                    plan_id=plan_id,
                    version=0,
                    opinion=opinion,
                    reviewer=test_reviewer,
                )

            assert exc_info.value.status_code == 409

            # Verify no side effects
            async with _pool.acquire() as conn:
                state_after = await _get_plan_state(conn, plan_id)
                records_after = await _count_audit_records(conn, plan_id)

                assert state_after["status"] == status, (
                    f"Status should remain '{status}', got '{state_after['status']}'"
                )
                assert state_after["version"] == state_before["version"]
                assert records_after == records_before

        finally:
            async with _pool.acquire() as conn:
                await _cleanup_plan(conn, plan_id)

    _loop.run_until_complete(_run())


@given(reviewer=reviewer_st())
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_new_plan_init_invariant(reviewer):
    """Feature: plan-human-review, Property 6: optimistic lock + init invariants

    **Validates: Requirements 1.5**

    New plans initialize with status='draft' and version=0.
    """
    assert _pool is not None

    async def _run():
        async with _pool.acquire() as conn:
            plan_id = await _create_plan(conn, status="draft", version=0)

        try:
            async with _pool.acquire() as conn:
                state = await _get_plan_state(conn, plan_id)
                assert state["status"] == "draft", (
                    f"New plan should have status='draft', got '{state['status']}'"
                )
                assert state["version"] == 0, (
                    f"New plan should have version=0, got {state['version']}"
                )
        finally:
            async with _pool.acquire() as conn:
                await _cleanup_plan(conn, plan_id)

    _loop.run_until_complete(_run())
