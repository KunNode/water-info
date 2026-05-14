"""Unit tests for the reviewer identity gate (_get_reviewer_from_request).

Table-driven tests verifying that all three review routes (PATCH /plans/{id},
POST /plans/{id}/approve, GET /plans/{id}/audits) correctly reject requests with:
1. Empty X-User-Id header
2. Empty X-Username header
3. X-User-Id or X-Username exceeding 255 characters
4. X-User-Id that doesn't exist in the user table

Each case asserts 400 with MISSING_IDENTITY or UNKNOWN_REVIEWER and no DB side effects.

Validates: Requirements 8.3, 8.4
Properties: P5
"""

from __future__ import annotations

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _build_db_mock(*, user_exists: bool = True):
    """Build a minimal DB mock for identity gate tests."""
    mock = SimpleNamespace(
        _get_pool=AsyncMock(return_value=object()),
        ensure_plan_tables=AsyncMock(),
        ensure_conversation_tables=AsyncMock(),
        ensure_kb_tables=AsyncMock(),
        close=AsyncMock(),
        user_exists=AsyncMock(return_value=user_exists),
        get_emergency_plan=AsyncMock(return_value={
            "plan_id": "plan-001",
            "plan_name": "测试预案",
            "risk_level": "high",
            "trigger_conditions": "test",
            "status": "draft",
            "session_id": "s-001",
            "summary": "test",
            "version": 0,
        }),
        get_plan_actions=AsyncMock(return_value=[]),
        get_plan_resources=AsyncMock(return_value=[]),
        get_plan_notifications=AsyncMock(return_value=[]),
        list_plan_audits=AsyncMock(return_value={"planId": "plan-001", "records": []}),
        save_emergency_plan=AsyncMock(),
        save_resource_allocations=AsyncMock(),
        save_notifications=AsyncMock(),
    )
    return mock


def _build_session_mock():
    return SimpleNamespace(
        get_history=AsyncMock(return_value=[]),
        save_turn=AsyncMock(),
        close=AsyncMock(),
    )


# The three routes under test
ROUTES = [
    ("PATCH", "/api/v1/plans/plan-001", {"version": 0, "summary": "new"}),
    ("POST", "/api/v1/plans/plan-001/approve", {"version": 0, "opinion": "ok"}),
    ("GET", "/api/v1/plans/plan-001/audits", None),
]


# --- MISSING_IDENTITY cases (empty headers or exceeding 255 chars) ---

MISSING_IDENTITY_CASES = [
    # (description, headers)
    ("empty X-User-Id", {"X-User-Id": "", "X-Username": "admin"}),
    ("missing X-User-Id", {"X-Username": "admin"}),
    ("empty X-Username", {"X-User-Id": "u-1", "X-Username": ""}),
    ("missing X-Username", {"X-User-Id": "u-1"}),
    ("X-User-Id exceeds 255 chars", {"X-User-Id": "u" * 256, "X-Username": "admin"}),
    ("X-Username exceeds 255 chars", {"X-User-Id": "u-1", "X-Username": "n" * 256}),
]


@pytest.mark.parametrize(
    "route_method,route_path,route_body",
    ROUTES,
    ids=["patch-edit", "post-approve", "get-audits"],
)
@pytest.mark.parametrize(
    "case_desc,headers",
    MISSING_IDENTITY_CASES,
    ids=[c[0] for c in MISSING_IDENTITY_CASES],
)
def test_missing_identity_returns_400(route_method, route_path, route_body, case_desc, headers):
    """Routes reject requests with missing/empty/overlength identity headers."""
    db_mock = _build_db_mock(user_exists=True)

    with ExitStack() as stack:
        stack.enter_context(patch("app.main.get_db_service", return_value=db_mock))
        stack.enter_context(patch("app.services.session.get_session_service", return_value=_build_session_mock()))
        client = stack.enter_context(TestClient(app))

        if route_method == "GET":
            response = client.get(route_path, headers=headers)
        elif route_method == "PATCH":
            response = client.patch(route_path, json=route_body, headers=headers)
        elif route_method == "POST":
            response = client.post(route_path, json=route_body, headers=headers)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["errorCode"] == "MISSING_IDENTITY"

    # DB should have no side effects: no plan writes, no audit writes
    db_mock.save_emergency_plan.assert_not_awaited()
    db_mock.list_plan_audits.assert_not_awaited()


# --- UNKNOWN_REVIEWER cases (user_id not in user table) ---

@pytest.mark.parametrize(
    "route_method,route_path,route_body",
    ROUTES,
    ids=["patch-edit", "post-approve", "get-audits"],
)
def test_unknown_reviewer_returns_400(route_method, route_path, route_body):
    """Routes reject requests when X-User-Id doesn't exist in the user table."""
    db_mock = _build_db_mock(user_exists=False)
    headers = {"X-User-Id": "nonexistent-user-999", "X-Username": "ghost"}

    with ExitStack() as stack:
        stack.enter_context(patch("app.main.get_db_service", return_value=db_mock))
        stack.enter_context(patch("app.services.session.get_session_service", return_value=_build_session_mock()))
        client = stack.enter_context(TestClient(app))

        if route_method == "GET":
            response = client.get(route_path, headers=headers)
        elif route_method == "PATCH":
            response = client.patch(route_path, json=route_body, headers=headers)
        elif route_method == "POST":
            response = client.post(route_path, json=route_body, headers=headers)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["errorCode"] == "UNKNOWN_REVIEWER"

    # user_exists was called with the provided user_id
    db_mock.user_exists.assert_awaited_once_with("nonexistent-user-999")

    # No business logic executed
    db_mock.save_emergency_plan.assert_not_awaited()
    db_mock.list_plan_audits.assert_not_awaited()
