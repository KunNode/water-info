"""End-to-end smoke test for the plan human review workflow.

Validates: Requirements 1.5, 3.2, 4.3, 4.4, 7.1, 7.2, 7.3, 7.4, 7.5
Properties: P3, P5, P6

Flow:
  1. Seed a draft plan in the database
  2. PATCH /api/v1/plans/{id} — modify summary + add an action
  3. PATCH /api/v1/plans/{id} — accumulate more draft diffs (modify summary again)
  4. POST /api/v1/plans/{id}/approve — with a valid opinion
  5. GET /api/v1/plans/{id}/audits — assert exactly one audit record with correct data

This test requires a live PostgreSQL database. Skipped if DB is not reachable.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

try:
    import asyncpg
except ImportError:
    asyncpg = None  # type: ignore[assignment]


# ── Database connectivity check (same pattern as test_audit_invariants_pbt.py) ─


def _get_dsn_params() -> dict:
    return {
        "host": os.environ.get("PG_HOST", "localhost"),
        "port": int(os.environ.get("PG_PORT", "5432")),
        "database": os.environ.get("PG_DATABASE", "water_info"),
        "user": os.environ.get("PG_USER", "postgres"),
        "password": os.environ.get("PG_PASSWORD", "postgres"),
    }


def _can_connect() -> bool:
    if asyncpg is None:
        return False
    try:
        loop = asyncio.new_event_loop()
        try:
            async def _check():
                conn = await asyncpg.connect(**_get_dsn_params(), timeout=5)
                await conn.close()
                return True
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


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def _event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def test_user_id(_event_loop):
    """Ensure a test user exists in the user table and return its ID."""
    async def _setup():
        conn = await asyncpg.connect(**_get_dsn_params(), timeout=5)
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS "user" (
                    id BIGSERIAL PRIMARY KEY,
                    username VARCHAR(255) NOT NULL DEFAULT ''
                )
            """)
            row = await conn.fetchrow('SELECT id FROM "user" LIMIT 1')
            if row:
                return str(row["id"])
            uid = await conn.fetchval(
                'INSERT INTO "user" (username) VALUES ($1) RETURNING id',
                "smoke_test_user",
            )
            return str(uid)
        finally:
            await conn.close()

    return _event_loop.run_until_complete(_setup())


@pytest.fixture()
def plan_id(_event_loop):
    """Seed a fresh draft plan and clean up after the test."""
    pid = f"smoke-{uuid.uuid4().hex[:12]}"

    async def _seed():
        conn = await asyncpg.connect(**_get_dsn_params(), timeout=5)
        try:
            await conn.execute(
                "INSERT INTO emergency_plan "
                "(plan_id, plan_name, summary, status, version) "
                "VALUES ($1, $2, $3, $4, $5)",
                pid, "Smoke Test Plan", "原始摘要内容", "draft", 0,
            )
        finally:
            await conn.close()

    async def _cleanup():
        conn = await asyncpg.connect(**_get_dsn_params(), timeout=5)
        try:
            # Disable immutability triggers to allow cascade delete
            await conn.execute(
                "ALTER TABLE plan_audit_change DISABLE TRIGGER trg_plan_audit_change_immutable"
            )
            await conn.execute(
                "ALTER TABLE plan_audit_record DISABLE TRIGGER trg_plan_audit_record_immutable"
            )
            await conn.execute(
                "DELETE FROM emergency_plan WHERE plan_id = $1", pid
            )
            await conn.execute(
                "ALTER TABLE plan_audit_record ENABLE TRIGGER trg_plan_audit_record_immutable"
            )
            await conn.execute(
                "ALTER TABLE plan_audit_change ENABLE TRIGGER trg_plan_audit_change_immutable"
            )
        finally:
            await conn.close()

    _event_loop.run_until_complete(_seed())
    yield pid
    _event_loop.run_until_complete(_cleanup())


@pytest.fixture()
def client():
    """Create a TestClient connected to the real app (real DB)."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c


# ── Smoke test ────────────────────────────────────────────────────────────────


def test_full_review_workflow(client, plan_id, test_user_id):
    """End-to-end: seed draft → edit twice → approve → verify audit record."""
    headers = {"X-User-Id": test_user_id, "X-Username": "smoke_tester"}

    # ── Step 1: PATCH — modify summary + add an action ────────────────────
    patch1 = {
        "version": 0,
        "summary": "第一次修改后的摘要",
        "actions": {
            "upsert": [
                {
                    "actionId": None,
                    "description": "新增巡查任务",
                    "priority": 1,
                    "assignee": "防汛办",
                    "status": "pending",
                }
            ],
            "delete": [],
        },
    }
    resp1 = client.patch(
        f"/api/v1/plans/{plan_id}", json=patch1, headers=headers
    )
    assert resp1.status_code == 200, f"PATCH 1 failed: {resp1.text}"
    data1 = resp1.json()
    assert data1["version"] == 1
    assert data1["summary"] == "第一次修改后的摘要"

    # Find the actionId that was created (response uses camelCase)
    actions = data1.get("actions", [])
    assert len(actions) == 1, f"Expected 1 action, got {len(actions)}"
    assert actions[0]["actionId"] is not None

    # ── Step 2: PATCH — modify summary again (accumulate diffs) ───────────
    patch2 = {
        "version": 1,
        "summary": "第二次修改后的最终摘要",
    }
    resp2 = client.patch(
        f"/api/v1/plans/{plan_id}", json=patch2, headers=headers
    )
    assert resp2.status_code == 200, f"PATCH 2 failed: {resp2.text}"
    data2 = resp2.json()
    assert data2["version"] == 2
    assert data2["summary"] == "第二次修改后的最终摘要"

    # ── Step 3: POST approve ──────────────────────────────────────────────
    approve_body = {
        "version": 2,
        "opinion": "审核通过，内容已确认无误。",
    }
    resp3 = client.post(
        f"/api/v1/plans/{plan_id}/approve", json=approve_body, headers=headers
    )
    assert resp3.status_code == 200, f"Approve failed: {resp3.text}"
    data3 = resp3.json()
    assert data3["plan_id"] == plan_id
    assert data3["status"] == "approved"
    assert data3["version"] == 3
    assert data3["audit_record_id"] is not None

    # ── Step 4: GET audits — verify the audit record ──────────────────────
    resp4 = client.get(
        f"/api/v1/plans/{plan_id}/audits", headers=headers
    )
    assert resp4.status_code == 200, f"GET audits failed: {resp4.text}"
    data4 = resp4.json()

    records = data4["records"]
    assert len(records) == 1, f"Expected exactly 1 audit record, got {len(records)}"

    record = records[0]
    assert record["action"] == "approve"
    assert record["from_status"] == "draft"
    assert record["to_status"] == "approved"
    assert record["reviewer_user_id"] == test_user_id
    assert record["reviewer_username"] == "smoke_tester"
    assert record["opinion"] == "审核通过，内容已确认无误。"
    assert record["from_version"] == 2
    assert record["to_version"] == 3

    # Verify changes cover the union of both edits
    changes = record["changes"]
    assert len(changes) > 0, "Expected at least one change entry"

    field_paths = {c["field_path"] for c in changes}

    # Summary was modified (twice, but the audit should reflect the diff from
    # initial to final — the two edits are accumulated as draft entries)
    assert "summary" in field_paths, f"Expected 'summary' in changes, got {field_paths}"

    # The new action should appear as an 'add' entry
    action_add_entries = [
        c for c in changes
        if c["change_type"] == "add" and "actions" in c["field_path"]
    ]
    assert len(action_add_entries) >= 1, (
        f"Expected at least one action 'add' change, got changes: {changes}"
    )

    # Verify old/new values for summary changes
    summary_changes = [c for c in changes if c["field_path"] == "summary"]
    # There may be multiple summary change entries (one per edit call) since
    # draft entries are accumulated per-call, not merged.
    assert len(summary_changes) >= 1
    # The first summary change should have old_value = original
    first_summary = summary_changes[0]
    assert first_summary["old_value"] == "原始摘要内容"
    assert first_summary["new_value"] == "第一次修改后的摘要"

    # If there are two summary changes, the second reflects the second edit
    if len(summary_changes) >= 2:
        second_summary = summary_changes[1]
        assert second_summary["old_value"] == "第一次修改后的摘要"
        assert second_summary["new_value"] == "第二次修改后的最终摘要"
