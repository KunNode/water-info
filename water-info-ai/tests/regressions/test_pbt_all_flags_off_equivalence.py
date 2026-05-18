"""Property 4: All-flags-off byte-for-byte equivalence.

Feature: supervisor-autogen-enhancements, Property 4: All-flags-off
byte-for-byte equivalence.

With all five enhancement flags ``false``, every SSE event emitted by the
streaming flood-query endpoint must be byte-identical to the frozen baseline
fixture captured in Task 2.1.  A metamorphic variant confirms that toggling
any single flag ``false → true → false`` on the same input reproduces the
identical output.
"""

from __future__ import annotations

import os
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.regressions.conftest import (
    FIXTURES_DIR,
    SCENARIOS,
    BaselineRecorder,
    mask_timestamps,
    sort_audit_rows,
    sse_lines_to_records,
)
from tests.regressions._capture_baselines import (
    StubGraph,
    _build_db_mock,
    _build_session_mock,
    _SCENARIO_BUILDERS,
)

# All five enhancement flags that must be off for the baseline path.
_FLAGS = (
    "OTEL_ENABLED",
    "AGENT_CONTRACTS_ENABLED",
    "DYNAMIC_TOPOLOGY_ENABLED",
    "HITL_ENABLED",
    "LANGGRAPH_POSTGRES_ENABLED",
)


def _run_scenario(scenario: str) -> dict[str, Any]:
    """Drive the SSE endpoint for *scenario* and return the masked payload."""
    config = _SCENARIO_BUILDERS[scenario]
    db_mock = _build_db_mock()
    session_mock = _build_session_mock()
    graph = StubGraph(stream_events=config["stream_events"]())

    with ExitStack() as stack:
        stack.enter_context(patch("app.main.get_db_service", return_value=db_mock))
        stack.enter_context(patch("app.main.flood_response_graph", graph))
        stack.enter_context(
            patch("app.services.session.get_session_service", return_value=session_mock)
        )
        client = stack.enter_context(TestClient(app))
        with client.stream(
            "POST",
            "/api/v1/flood/query/stream",
            json={"query": config["query"], "session_id": config["session_id"]},
        ) as response:
            assert response.status_code == 200, response.read()
            body = "".join(response.iter_text())

    message_metadata: dict[str, Any] = {}
    if db_mock.update_message_content.await_args is not None:
        message_metadata = (
            db_mock.update_message_content.await_args.kwargs.get("metadata") or {}
        )

    recorder = BaselineRecorder(scenario=scenario, regenerate=False)
    recorder.record(
        sse_body=body,
        message_metadata=message_metadata,
        audit_rows=[],
    )
    return recorder.captured_payload()


# Need to import app after env setup
from app.main import app  # noqa: E402


class TestAllFlagsOffEquivalence:
    """P4: byte-for-byte equivalence with all flags off."""

    @pytest.fixture(autouse=True)
    def _force_flags_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure all five enhancement flags are ``false``."""
        for flag in _FLAGS:
            monkeypatch.setenv(flag, "false")

    @pytest.mark.parametrize("scenario", SCENARIOS)
    def test_scenario_matches_baseline(self, scenario: str) -> None:
        """Each scenario's captured payload equals the on-disk fixture."""
        fixture_path = FIXTURES_DIR / f"sse_baseline_{scenario}.json"
        assert fixture_path.exists(), (
            f"baseline fixture missing: {fixture_path}. "
            "Run `uv run python -m tests.regressions._capture_baselines` to generate."
        )
        import json

        expected = json.loads(fixture_path.read_text(encoding="utf-8"))
        actual = _run_scenario(scenario)
        assert actual == expected, (
            f"Scenario {scenario!r}: SSE output diverged from baseline.\n"
            f"Expected {len(expected.get('sse_records', []))} SSE records, "
            f"got {len(actual.get('sse_records', []))}."
        )

    @pytest.mark.parametrize("scenario", SCENARIOS)
    def test_flag_toggle_metamorphic(self, scenario: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """Toggling one flag false→true→false reproduces identical output.

        This is the metamorphic variant of P4: enabling a single flag and
        then disabling it must not change the output.
        """
        baseline = _run_scenario(scenario)

        for flag in _FLAGS:
            monkeypatch.setenv(flag, "true")
            # Force settings reload by clearing lru_cache
            from app.config import get_settings

            get_settings.cache_clear()
            # Run with flag on — we don't compare this output, just ensure
            # the state machine is exercised.
            _run_scenario(scenario)

            # Flip back off
            monkeypatch.setenv(flag, "false")
            get_settings.cache_clear()
            after = _run_scenario(scenario)
            assert after == baseline, (
                f"Scenario {scenario!r}: toggling {flag} off→on→off changed output."
            )
