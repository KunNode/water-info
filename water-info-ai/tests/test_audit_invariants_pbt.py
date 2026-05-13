"""Property-based test for audit invariants after edit/approve.

Feature: plan-human-review, Property 5: audit record completeness & uniqueness

Validates: Requirements 4.4, 7.1, 7.2, 7.3, 7.4, 8.2

Property 5: For any successfully completed `edit_draft → … → approve` or single
`edit_approved`, assert:
(a) Exactly one new plan_audit_record is created;
(b) reviewer_user_id/username byte-equal to request headers;
(c) approve path: opinion == stripped; edit_after_approve path: opinion IS NULL;
(d) The diff set (plan_audit_change rows) equals the diff computed by diff_plan
    between the initial and final snapshots.

Uses hypothesis generators to produce arbitrary patch sequences + final approve.

This test requires a live PostgreSQL database with the plan tables bootstrapped.
It will be skipped if the database is not reachable.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from copy import deepcopy
from typing import Any

import pytest

try:
    import asyncpg
except ImportError:
    asyncpg = None  # type: ignore[assignment]

from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from app.services.plan_diff import (
    ActionItem,
    ChangeEntry,
    NotificationItem,
    PlanSnapshot,
    ResourceItem,
    diff_plan,
)
from app.services.plan_review import PlanReviewService, Reviewer


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
    """Ensure all required tables and columns exist.

    Uses ADD COLUMN IF NOT EXISTS for idempotency on existing schemas.
    """
    # Ensure version column exists on emergency_plan
    await conn.execute("""
        ALTER TABLE emergency_plan ADD COLUMN IF NOT EXISTS version INT NOT NULL DEFAULT 0
    """)
    # Ensure user table exists
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

_priority_st = st.integers(min_value=1, max_value=5)


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
def opinion_st(draw) -> str:
    """Generate a valid opinion (strip length 1-500)."""
    # Generate core text (1-500 chars)
    core = draw(st.text(
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
        min_size=1,
        max_size=100,
    ))
    # Optionally add leading/trailing whitespace
    prefix = draw(st.sampled_from(["", " ", "  ", "\t"]))
    suffix = draw(st.sampled_from(["", " ", "  ", "\t"]))
    return prefix + core + suffix


@st.composite
def actions_patch_st(draw, existing_action_ids: list[str]) -> dict:
    """Generate a valid actions patch given existing action IDs."""
    patch: dict[str, list] = {"upsert": [], "delete": []}

    # Delete subset of existing
    if existing_action_ids:
        delete_ids = draw(st.lists(
            st.sampled_from(existing_action_ids),
            max_size=min(len(existing_action_ids), 2),
            unique=True,
        ))
        patch["delete"] = delete_ids
    else:
        delete_ids = []

    remaining = [aid for aid in existing_action_ids if aid not in delete_ids]

    # Modify some existing
    if remaining:
        modify_ids = draw(st.lists(
            st.sampled_from(remaining),
            max_size=min(len(remaining), 2),
            unique=True,
        ))
        for aid in modify_ids:
            patch["upsert"].append({
                "actionId": aid,
                "description": draw(_short_text),
                "priority": draw(_priority_st),
                "assignee": draw(_short_text),
                "status": draw(st.sampled_from(["pending", "in_progress", "done"])),
            })

    # Add new
    new_count = draw(st.integers(min_value=0, max_value=2))
    for _ in range(new_count):
        new_id = f"a-{draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789', min_size=3, max_size=6))}"
        assume(new_id not in existing_action_ids)
        patch["upsert"].append({
            "actionId": new_id,
            "description": draw(_short_text),
            "priority": draw(_priority_st),
            "assignee": draw(_short_text),
            "status": draw(st.sampled_from(["pending", "in_progress", "done"])),
        })

    return patch


@st.composite
def single_patch_st(draw, existing_action_ids: list[str]) -> dict:
    """Generate a single valid patch for a plan."""
    patch: dict[str, Any] = {}

    # Optionally change summary
    if draw(st.booleans()):
        patch["summary"] = draw(_pg_safe_text)

    # Optionally change actions
    if draw(st.booleans()):
        patch["actions"] = draw(actions_patch_st(existing_action_ids))

    return patch


@st.composite
def patch_sequence_st(draw) -> list[dict]:
    """Generate a sequence of 1-3 patches (simulating multiple edit_draft calls)."""
    # Start with no existing actions (fresh plan)
    existing_ids: list[str] = []
    patches = []
    count = draw(st.integers(min_value=1, max_value=3))
    for _ in range(count):
        p = draw(single_patch_st(existing_ids))
        patches.append(p)
        # Track new action IDs added by this patch
        if "actions" in p:
            for item in p["actions"].get("upsert", []):
                aid = item.get("actionId") or item.get("action_id")
                if aid and aid not in existing_ids:
                    existing_ids.append(aid)
            for aid in p["actions"].get("delete", []):
                if aid in existing_ids:
                    existing_ids.remove(aid)
    return patches


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
            # Find or create a test user in the user table
            row = await conn.fetchrow('SELECT id FROM "user" LIMIT 1')
            if row:
                _test_user_id = str(row["id"])
            else:
                uid = await conn.fetchval(
                    'INSERT INTO "user" (username) VALUES ($1) RETURNING id',
                    "pbt_audit_tester",
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


async def _create_fresh_plan(conn: asyncpg.Connection) -> str:
    """Create a fresh draft plan with unique ID. Returns plan_id."""
    plan_id = f"pbt-audit-{uuid.uuid4().hex[:12]}"
    await conn.execute(
        "INSERT INTO emergency_plan (plan_id, plan_name, summary, status, version) "
        "VALUES ($1, $2, $3, $4, $5)",
        plan_id, "PBT Audit Test Plan", "Initial summary", "draft", 0,
    )
    return plan_id


async def _cleanup_plan(conn: asyncpg.Connection, plan_id: str) -> None:
    """Remove test plan and all related data (cascades)."""
    await conn.execute("DELETE FROM emergency_plan WHERE plan_id = $1", plan_id)


async def _count_audit_records(conn: asyncpg.Connection, plan_id: str) -> int:
    """Count audit records for a plan."""
    return await conn.fetchval(
        "SELECT COUNT(*) FROM plan_audit_record WHERE plan_id = $1", plan_id
    )


async def _get_audit_records(conn: asyncpg.Connection, plan_id: str) -> list[dict]:
    """Get all audit records for a plan."""
    rows = await conn.fetch(
        "SELECT * FROM plan_audit_record WHERE plan_id = $1 ORDER BY id ASC", plan_id
    )
    return [dict(r) for r in rows]


async def _get_audit_changes(conn: asyncpg.Connection, audit_id: int) -> list[dict]:
    """Get all audit change entries for an audit record."""
    rows = await conn.fetch(
        "SELECT * FROM plan_audit_change WHERE audit_id = $1 ORDER BY id ASC", audit_id
    )
    return [dict(r) for r in rows]


async def _build_snapshot_from_db(conn: asyncpg.Connection, plan_id: str) -> PlanSnapshot:
    """Build a PlanSnapshot from current DB state."""
    row = await conn.fetchrow(
        "SELECT summary FROM emergency_plan WHERE plan_id = $1", plan_id
    )
    summary = row["summary"] if row else ""

    actions_rows = await conn.fetch(
        "SELECT action_id, description, priority, responsible_dept, status "
        "FROM emergency_action WHERE plan_id = $1 ORDER BY priority ASC",
        plan_id,
    )
    resources_rows = await conn.fetch(
        "SELECT id, resource_type, resource_name, quantity, source_location "
        "FROM resource_allocation WHERE plan_id = $1 ORDER BY id ASC",
        plan_id,
    )
    notifications_rows = await conn.fetch(
        "SELECT id, channel, target, content, status "
        "FROM notification_record WHERE plan_id = $1 ORDER BY id ASC",
        plan_id,
    )

    actions = [
        ActionItem(
            action_id=r["action_id"],
            description=r["description"],
            priority=r["priority"],
            assignee=r.get("responsible_dept") or "",
            status=r["status"],
        )
        for r in actions_rows
    ]
    resources = [
        ResourceItem(
            resource_id=r["id"],
            type=r["resource_type"],
            name=r["resource_name"],
            quantity=r["quantity"],
            location=r.get("source_location") or "",
        )
        for r in resources_rows
    ]
    notifications = [
        NotificationItem(
            notification_id=r["id"],
            channel=r["channel"],
            target=r["target"],
            message=r.get("content") or "",
            status=r["status"],
        )
        for r in notifications_rows
    ]

    return PlanSnapshot(
        summary=summary,
        actions=actions,
        resources=resources,
        notifications=notifications,
    )


# ── Property tests ────────────────────────────────────────────────────────────


@given(
    patches=patch_sequence_st(),
    reviewer=reviewer_st(),
    opinion=opinion_st(),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_audit_invariants_approve_path(patches, reviewer, opinion):
    """Feature: plan-human-review, Property 5: audit record completeness & uniqueness

    **Validates: Requirements 4.4, 7.1, 7.2, 7.3, 7.4, 8.2**

    For any sequence of edit_draft calls followed by approve:
    (a) Exactly one new plan_audit_record is created;
    (b) reviewer_user_id/username byte-equal to the reviewer used;
    (c) opinion == opinion.strip();
    (d) The audit changes match the diff between initial and final snapshots.
    """
    assert _pool is not None and _test_user_id is not None

    # Use the test user ID that exists in the DB
    test_reviewer = Reviewer(user_id=_test_user_id, username=reviewer.username)

    async def _run():
        service = PlanReviewService(_pool)
        async with _pool.acquire() as conn:
            plan_id = await _create_fresh_plan(conn)

        try:
            # Capture initial snapshot
            async with _pool.acquire() as conn:
                initial_snapshot = await _build_snapshot_from_db(conn, plan_id)

            # Apply patch sequence via edit_draft
            current_version = 0
            for patch in patches:
                if not patch:  # skip empty patches
                    continue
                try:
                    result = await service.edit_draft(
                        plan_id=plan_id,
                        version=current_version,
                        patch=patch,
                        reviewer=test_reviewer,
                    )
                    current_version = result["version"]
                except Exception:
                    # If a patch fails validation, skip it
                    pass

            # Capture pre-approve snapshot
            async with _pool.acquire() as conn:
                pre_approve_snapshot = await _build_snapshot_from_db(conn, plan_id)

            # Count audit records before approve
            async with _pool.acquire() as conn:
                records_before = await _count_audit_records(conn, plan_id)

            # Approve
            result = await service.approve(
                plan_id=plan_id,
                version=current_version,
                opinion=opinion,
                reviewer=test_reviewer,
            )

            # ── Assertions ────────────────────────────────────────────────

            async with _pool.acquire() as conn:
                # (a) Exactly one new plan_audit_record
                records_after = await _count_audit_records(conn, plan_id)
                assert records_after == records_before + 1, (
                    f"Expected exactly 1 new audit record, got {records_after - records_before}"
                )

                # Get the new audit record
                all_records = await _get_audit_records(conn, plan_id)
                new_record = all_records[-1]  # last one is the newest

                # (b) reviewer_user_id/username byte-equal
                assert new_record["reviewer_user_id"] == test_reviewer.user_id, (
                    f"reviewer_user_id mismatch: {new_record['reviewer_user_id']!r} != {test_reviewer.user_id!r}"
                )
                assert new_record["reviewer_username"] == test_reviewer.username, (
                    f"reviewer_username mismatch: {new_record['reviewer_username']!r} != {test_reviewer.username!r}"
                )

                # (c) approve path: opinion == stripped
                assert new_record["opinion"] == opinion.strip(), (
                    f"opinion mismatch: {new_record['opinion']!r} != {opinion.strip()!r}"
                )
                assert new_record["action"] == "approve"

                # (d) Diff set matches diff_plan(initial, pre_approve)
                expected_diff = diff_plan(initial_snapshot, pre_approve_snapshot)
                audit_changes = await _get_audit_changes(conn, new_record["id"])

                expected_paths = {
                    (c.field_path, c.change_type) for c in expected_diff
                }
                actual_paths = {
                    (c["field_path"], c["change_type"]) for c in audit_changes
                }

                assert expected_paths == actual_paths, (
                    f"Audit changes don't match expected diff.\n"
                    f"Expected: {sorted(expected_paths)}\n"
                    f"Actual:   {sorted(actual_paths)}"
                )

                # Also verify old_value/new_value for each change
                expected_by_path = {
                    (c.field_path, c.change_type): c for c in expected_diff
                }
                for ac in audit_changes:
                    key = (ac["field_path"], ac["change_type"])
                    exp = expected_by_path.get(key)
                    assert exp is not None, f"Unexpected audit change: {key}"
                    assert ac["old_value"] == exp.old_value, (
                        f"old_value mismatch for {key}: {ac['old_value']!r} != {exp.old_value!r}"
                    )
                    assert ac["new_value"] == exp.new_value, (
                        f"new_value mismatch for {key}: {ac['new_value']!r} != {exp.new_value!r}"
                    )

        finally:
            # Cleanup
            async with _pool.acquire() as conn:
                await _cleanup_plan(conn, plan_id)

    _loop.run_until_complete(_run())


@given(
    patch=st.builds(
        lambda s, a: {"summary": s} if not a else {"summary": s, "actions": a},
        s=_pg_safe_text,
        a=st.just(None),
    ),
    reviewer=reviewer_st(),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_audit_invariants_edit_approved_path(patch, reviewer):
    """Feature: plan-human-review, Property 5: audit record completeness & uniqueness

    **Validates: Requirements 4.4, 7.1, 7.2, 7.3, 7.4, 8.2**

    For any single edit_approved call:
    (a) Exactly one new plan_audit_record is created;
    (b) reviewer_user_id/username byte-equal to the reviewer used;
    (c) edit_after_approve path: opinion IS NULL;
    (d) The audit changes match diff_plan(before, after).
    """
    assert _pool is not None and _test_user_id is not None

    test_reviewer = Reviewer(user_id=_test_user_id, username=reviewer.username)

    async def _run():
        service = PlanReviewService(_pool)

        # Create a plan in approved state
        async with _pool.acquire() as conn:
            plan_id = f"pbt-audit-ea-{uuid.uuid4().hex[:12]}"
            await conn.execute(
                "INSERT INTO emergency_plan (plan_id, plan_name, summary, status, version) "
                "VALUES ($1, $2, $3, $4, $5)",
                plan_id, "PBT Edit Approved Test", "Original summary", "approved", 0,
            )

        try:
            # Capture initial snapshot
            async with _pool.acquire() as conn:
                initial_snapshot = await _build_snapshot_from_db(conn, plan_id)
                records_before = await _count_audit_records(conn, plan_id)

            # Perform edit_approved
            result = await service.edit_approved(
                plan_id=plan_id,
                version=0,
                patch=patch,
                reviewer=test_reviewer,
            )

            # ── Assertions ────────────────────────────────────────────────

            async with _pool.acquire() as conn:
                # Capture final snapshot
                final_snapshot = await _build_snapshot_from_db(conn, plan_id)

                # (a) Exactly one new plan_audit_record
                records_after = await _count_audit_records(conn, plan_id)
                assert records_after == records_before + 1, (
                    f"Expected exactly 1 new audit record, got {records_after - records_before}"
                )

                # Get the new audit record
                all_records = await _get_audit_records(conn, plan_id)
                new_record = all_records[-1]

                # (b) reviewer_user_id/username byte-equal
                assert new_record["reviewer_user_id"] == test_reviewer.user_id, (
                    f"reviewer_user_id mismatch: {new_record['reviewer_user_id']!r} != {test_reviewer.user_id!r}"
                )
                assert new_record["reviewer_username"] == test_reviewer.username, (
                    f"reviewer_username mismatch: {new_record['reviewer_username']!r} != {test_reviewer.username!r}"
                )

                # (c) edit_after_approve path: opinion IS NULL
                assert new_record["opinion"] is None, (
                    f"opinion should be NULL for edit_after_approve, got: {new_record['opinion']!r}"
                )
                assert new_record["action"] == "edit_after_approve"

                # (d) Diff set matches diff_plan(initial, final)
                expected_diff = diff_plan(initial_snapshot, final_snapshot)
                audit_changes = await _get_audit_changes(conn, new_record["id"])

                expected_paths = {
                    (c.field_path, c.change_type) for c in expected_diff
                }
                actual_paths = {
                    (c["field_path"], c["change_type"]) for c in audit_changes
                }

                assert expected_paths == actual_paths, (
                    f"Audit changes don't match expected diff.\n"
                    f"Expected: {sorted(expected_paths)}\n"
                    f"Actual:   {sorted(actual_paths)}"
                )

                # Verify old_value/new_value
                expected_by_path = {
                    (c.field_path, c.change_type): c for c in expected_diff
                }
                for ac in audit_changes:
                    key = (ac["field_path"], ac["change_type"])
                    exp = expected_by_path.get(key)
                    assert exp is not None, f"Unexpected audit change: {key}"
                    assert ac["old_value"] == exp.old_value, (
                        f"old_value mismatch for {key}: {ac['old_value']!r} != {exp.old_value!r}"
                    )
                    assert ac["new_value"] == exp.new_value, (
                        f"new_value mismatch for {key}: {ac['new_value']!r} != {exp.new_value!r}"
                    )

        finally:
            async with _pool.acquire() as conn:
                await _cleanup_plan(conn, plan_id)

    _loop.run_until_complete(_run())
