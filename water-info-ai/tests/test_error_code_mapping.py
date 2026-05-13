"""Table-driven integration test for error-code mapping.

Covers all error codes from design.md Error Handling table:
  400 MISSING_IDENTITY — X-User-Id/X-Username missing or overlength
  400 UNKNOWN_REVIEWER — user_id not in user table
  404 PLAN_NOT_FOUND / ENTRY_NOT_FOUND — plan or sub-entry doesn't exist
  409 STATE_CONFLICT — current state doesn't allow the action
  409 VERSION_CONFLICT — optimistic lock failure
  422 VALIDATION_FAILED — field validation failure

For each case, asserts HTTP status code and response body `detail.errorCode` match.

Validates: Requirements 3.6, 3.7, 3.8, 4.5, 4.6, 4.7, 6.1, 7.8, 8.3, 8.4
Properties: P2, P3, P4

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
                "error_code_test_user",
            )
            return str(uid)
        finally:
            await conn.close()

    return _event_loop.run_until_complete(_setup())


@pytest.fixture()
def draft_plan_id(_event_loop):
    """Seed a fresh draft plan and clean up after the test."""
    pid = f"errtest-{uuid.uuid4().hex[:12]}"

    async def _seed():
        conn = await asyncpg.connect(**_get_dsn_params(), timeout=5)
        try:
            await conn.execute(
                "INSERT INTO emergency_plan "
                "(plan_id, plan_name, summary, status, version) "
                "VALUES ($1, $2, $3, $4, $5)",
                pid, "Error Code Test Plan", "测试摘要", "draft", 0,
            )
        finally:
            await conn.close()

    async def _cleanup():
        conn = await asyncpg.connect(**_get_dsn_params(), timeout=5)
        try:
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
def executing_plan_id(_event_loop):
    """Seed a plan in 'executing' state for STATE_CONFLICT tests."""
    pid = f"errtest-exec-{uuid.uuid4().hex[:12]}"

    async def _seed():
        conn = await asyncpg.connect(**_get_dsn_params(), timeout=5)
        try:
            await conn.execute(
                "INSERT INTO emergency_plan "
                "(plan_id, plan_name, summary, status, version) "
                "VALUES ($1, $2, $3, $4, $5)",
                pid, "Executing Plan", "执行中预案", "executing", 3,
            )
        finally:
            await conn.close()

    async def _cleanup():
        conn = await asyncpg.connect(**_get_dsn_params(), timeout=5)
        try:
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


# ── Table-driven error code tests ────────────────────────────────────────────


class TestErrorCodeMapping:
    """Table-driven integration tests covering all error codes from design.md."""

    # ── 400 MISSING_IDENTITY ──────────────────────────────────────────────

    @pytest.mark.parametrize(
        "desc,headers",
        [
            ("empty X-User-Id", {"X-User-Id": "", "X-Username": "admin"}),
            ("missing X-User-Id", {"X-Username": "admin"}),
            ("empty X-Username", {"X-User-Id": "u-1", "X-Username": ""}),
            ("missing X-Username", {"X-User-Id": "u-1"}),
            ("X-User-Id exceeds 255", {"X-User-Id": "u" * 256, "X-Username": "admin"}),
            ("X-Username exceeds 255", {"X-User-Id": "u-1", "X-Username": "n" * 256}),
        ],
        ids=lambda x: x if isinstance(x, str) else "",
    )
    def test_400_missing_identity(self, client, draft_plan_id, desc, headers):
        """400 MISSING_IDENTITY: X-User-Id/X-Username missing or overlength."""
        resp = client.patch(
            f"/api/v1/plans/{draft_plan_id}",
            json={"version": 0, "summary": "new"},
            headers=headers,
        )
        assert resp.status_code == 400, f"[{desc}] Expected 400, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "MISSING_IDENTITY", f"[{desc}] Got errorCode: {detail['errorCode']}"

    # ── 400 UNKNOWN_REVIEWER ──────────────────────────────────────────────

    def test_400_unknown_reviewer(self, client, draft_plan_id):
        """400 UNKNOWN_REVIEWER: user_id not in user table."""
        headers = {"X-User-Id": "nonexistent-user-99999", "X-Username": "ghost"}
        resp = client.patch(
            f"/api/v1/plans/{draft_plan_id}",
            json={"version": 0, "summary": "new"},
            headers=headers,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "UNKNOWN_REVIEWER"

    # ── 404 PLAN_NOT_FOUND ────────────────────────────────────────────────

    def test_404_plan_not_found_patch(self, client, test_user_id):
        """404 PLAN_NOT_FOUND: plan doesn't exist (PATCH)."""
        headers = {"X-User-Id": test_user_id, "X-Username": "tester"}
        resp = client.patch(
            "/api/v1/plans/nonexistent-plan-xyz",
            json={"version": 0, "summary": "new"},
            headers=headers,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "PLAN_NOT_FOUND"

    def test_404_plan_not_found_approve(self, client, test_user_id):
        """404 PLAN_NOT_FOUND: plan doesn't exist (approve)."""
        headers = {"X-User-Id": test_user_id, "X-Username": "tester"}
        resp = client.post(
            "/api/v1/plans/nonexistent-plan-xyz/approve",
            json={"version": 0, "opinion": "ok"},
            headers=headers,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "PLAN_NOT_FOUND"

    def test_404_plan_not_found_audits(self, client, test_user_id):
        """404 PLAN_NOT_FOUND: plan doesn't exist (GET audits)."""
        headers = {"X-User-Id": test_user_id, "X-Username": "tester"}
        resp = client.get(
            "/api/v1/plans/nonexistent-plan-xyz/audits",
            headers=headers,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "PLAN_NOT_FOUND"

    # ── 404 ENTRY_NOT_FOUND ───────────────────────────────────────────────

    def test_404_entry_not_found(self, client, draft_plan_id, test_user_id):
        """404 ENTRY_NOT_FOUND: deleting a sub-entry that doesn't exist."""
        headers = {"X-User-Id": test_user_id, "X-Username": "tester"}
        resp = client.patch(
            f"/api/v1/plans/{draft_plan_id}",
            json={
                "version": 0,
                "actions": {"upsert": [], "delete": ["nonexistent-action-id"]},
            },
            headers=headers,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "ENTRY_NOT_FOUND"

    # ── 409 STATE_CONFLICT ────────────────────────────────────────────────

    def test_409_state_conflict_edit(self, client, executing_plan_id, test_user_id):
        """409 STATE_CONFLICT: editing a plan in 'executing' state."""
        headers = {"X-User-Id": test_user_id, "X-Username": "tester"}
        resp = client.patch(
            f"/api/v1/plans/{executing_plan_id}",
            json={"version": 3, "summary": "should fail"},
            headers=headers,
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "STATE_CONFLICT"

    def test_409_state_conflict_approve_non_draft(self, client, executing_plan_id, test_user_id):
        """409 STATE_CONFLICT: approving a plan not in 'draft' state."""
        headers = {"X-User-Id": test_user_id, "X-Username": "tester"}
        resp = client.post(
            f"/api/v1/plans/{executing_plan_id}/approve",
            json={"version": 3, "opinion": "should fail"},
            headers=headers,
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "STATE_CONFLICT"

    # ── 409 VERSION_CONFLICT ──────────────────────────────────────────────

    def test_409_version_conflict_edit(self, client, draft_plan_id, test_user_id):
        """409 VERSION_CONFLICT: optimistic lock failure on edit."""
        headers = {"X-User-Id": test_user_id, "X-Username": "tester"}
        # Plan is at version 0, submit with version 99
        resp = client.patch(
            f"/api/v1/plans/{draft_plan_id}",
            json={"version": 99, "summary": "stale edit"},
            headers=headers,
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "VERSION_CONFLICT"

    def test_409_version_conflict_approve(self, client, draft_plan_id, test_user_id):
        """409 VERSION_CONFLICT: optimistic lock failure on approve."""
        headers = {"X-User-Id": test_user_id, "X-Username": "tester"}
        # Plan is at version 0, submit with version 99
        resp = client.post(
            f"/api/v1/plans/{draft_plan_id}/approve",
            json={"version": 99, "opinion": "stale approve"},
            headers=headers,
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "VERSION_CONFLICT"

    # ── 422 VALIDATION_FAILED ─────────────────────────────────────────────

    def test_422_validation_failed_opinion_empty(self, client, draft_plan_id, test_user_id):
        """422 VALIDATION_FAILED: opinion is empty after strip."""
        headers = {"X-User-Id": test_user_id, "X-Username": "tester"}
        resp = client.post(
            f"/api/v1/plans/{draft_plan_id}/approve",
            json={"version": 0, "opinion": "   "},
            headers=headers,
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "VALIDATION_FAILED"

    def test_422_validation_failed_opinion_too_long(self, client, draft_plan_id, test_user_id):
        """422 VALIDATION_FAILED: opinion exceeds 500 chars after strip."""
        headers = {"X-User-Id": test_user_id, "X-Username": "tester"}
        resp = client.post(
            f"/api/v1/plans/{draft_plan_id}/approve",
            json={"version": 0, "opinion": "x" * 501},
            headers=headers,
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "VALIDATION_FAILED"

    def test_422_validation_failed_summary_too_long(self, client, draft_plan_id, test_user_id):
        """422 VALIDATION_FAILED: summary exceeds 50000 chars."""
        headers = {"X-User-Id": test_user_id, "X-Username": "tester"}
        resp = client.patch(
            f"/api/v1/plans/{draft_plan_id}",
            json={"version": 0, "summary": "x" * 50001},
            headers=headers,
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "VALIDATION_FAILED"

    def test_422_validation_failed_priority_out_of_range(self, client, draft_plan_id, test_user_id):
        """422 VALIDATION_FAILED: action priority out of 1-5 range."""
        headers = {"X-User-Id": test_user_id, "X-Username": "tester"}
        resp = client.patch(
            f"/api/v1/plans/{draft_plan_id}",
            json={
                "version": 0,
                "actions": {
                    "upsert": [{
                        "actionId": None,
                        "description": "test",
                        "priority": 99,
                        "assignee": "someone",
                        "status": "pending",
                    }],
                    "delete": [],
                },
            },
            headers=headers,
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "VALIDATION_FAILED"

    def test_422_validation_failed_required_field_missing(self, client, draft_plan_id, test_user_id):
        """422 VALIDATION_FAILED: required field (description) missing in action."""
        headers = {"X-User-Id": test_user_id, "X-Username": "tester"}
        resp = client.patch(
            f"/api/v1/plans/{draft_plan_id}",
            json={
                "version": 0,
                "actions": {
                    "upsert": [{
                        "actionId": None,
                        "description": "",
                        "priority": 1,
                        "assignee": "someone",
                        "status": "pending",
                    }],
                    "delete": [],
                },
            },
            headers=headers,
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        detail = resp.json()["detail"]
        assert detail["errorCode"] == "VALIDATION_FAILED"
