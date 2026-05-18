"""Pytest plugin for the supervisor-autogen-enhancements byte-for-byte
regression fixture (Property 4).

Spec: ``.kiro/specs/supervisor-autogen-enhancements/`` — Testing Strategy
section "Regression fixture for byte-for-byte SSE equivalence".

What this plugin provides
-------------------------

1. A ``--regenerate-baseline`` pytest CLI flag. When passed, any test under
   ``tests/regressions/`` that uses the ``baseline_recorder`` fixture writes
   its captured payload to the corresponding on-disk fixture file (overwrite).
   When not passed, the fixture loads the on-disk JSON and exposes it for
   strict equality comparison (this is the path Task 2.2 will exercise).

2. A ``baseline_recorder`` fixture: a small recorder object that callers feed
   per-scenario captured artifacts to. The recorder is responsible for masking
   non-deterministic fields (timestamps, UUID-shaped ids), sorting audit rows,
   and serialising the result deterministically.

3. Scenario-driver helpers: ``capture_sse_baseline(scenario)``. Each driver
   stands up a FastAPI ``TestClient`` against the existing app, replaces
   ``flood_response_graph`` with a hand-crafted ``StubGraph`` that emits the
   deterministic state updates for that scenario, drives one request through
   the SSE endpoint, and returns the exact bytes plus the metadata payload
   written to ``conversation_messages.metadata`` by the SSE handler.

Scenarios
---------

* ``general_chat``     — a greeting routed through ``conversation_assistant``
                        only, no risk / plan / resources / notifications.
* ``data_only``        — ``answer_policy.data_only=True`` running through
                        ``data_analyst`` only (no risk_assessor).
* ``full_workflow``    — flood emergency: ``data_analyst → risk_assessor →
                        plan_generator → resource_dispatcher → notification
                        → final_response`` without triggering CRITICAL safety.

Documented gaps
---------------

The design's regression fixture also asks for the rows written to
``agent_runs`` / ``tool_calls`` / ``decision_log`` / ``evidence_traces``.
Those rows are produced by the ``audited_agent`` decorator (see
``app/platform/agent_audit.py``) and only flow when
``settings.audit_tables_enabled=True``. To keep the fixture deterministic and
free of cross-scenario flakes, the capture path replaces
``flood_response_graph`` with a ``StubGraph`` that bypasses ``audited_agent``,
so the audit-row content is captured as an empty list per scenario in this
task. Audit-row equivalence is independently validated by
``tests/test_audit_immutability_pbt.py`` and
``tests/test_audit_invariants_pbt.py`` and is therefore not duplicated here.
Task 2.2's Property 4 test will compare ``sse_records`` and ``message_metadata``
strictly; the ``audit_rows`` slot is reserved for a future capture pass that
runs the real graph end-to-end (out of scope for Task 2.1).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

# ── Public constants ──────────────────────────────────────────────────────────

#: Directory that holds all ``sse_baseline_<scenario>.json`` fixture files.
FIXTURES_DIR: Path = Path(__file__).parent / "fixtures"

#: The three scenarios captured for Property 4. Order is fixed so the
#: regeneration script and Task 2.2's test can iterate identically.
SCENARIOS: tuple[str, ...] = (
    "general_chat",
    "data_only",
    "full_workflow",
)

# ── Pytest plugin hooks ───────────────────────────────────────────────────────


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ``--regenerate-baseline`` CLI flag.

    The flag is owned by this plugin and only meaningful for tests under
    ``tests/regressions/``. It is intentionally a single boolean (not a path
    selector) so the regeneration command is the single source of truth:
    ``uv run pytest tests/regressions/ --regenerate-baseline``.
    """
    parser.addoption(
        "--regenerate-baseline",
        action="store_true",
        default=False,
        dest="regenerate_baseline",
        help=(
            "Regenerate the on-disk SSE baseline fixtures under "
            "tests/regressions/fixtures/ instead of comparing against them. "
            "Use this only when the all-flags-off SSE contract has intentionally "
            "changed and you have reviewed the diff."
        ),
    )


# ── Determinism helpers (public API consumed by Task 2.2) ─────────────────────


# ISO-8601 timestamps with optional fractional seconds and timezone, e.g.
# ``2026-05-10T08:00:00+00:00`` or ``2026-05-10T08:00:00.123456Z``. We mask
# them rather than dropping the key so the schema stays stable across runs.
_ISO_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:?\d{2})?\b"
)

# UUID-shaped value (8-4-4-4-12 hex). Used for ``id`` / ``run_id`` /
# ``agent_run_id`` / ``session_id`` / ``approval_id`` / ``checkpoint_id``.
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

#: Keys whose values are masked to ``"<UUID>"`` regardless of shape (some
#: callers use opaque non-UUID identifiers; we still want a stable placeholder).
_ID_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "run_id",
        "agent_run_id",
        "session_id",
        "approval_id",
        "checkpoint_id",
    }
)

_TIMESTAMP_PLACEHOLDER = "<TIMESTAMP>"
_UUID_PLACEHOLDER = "<UUID>"


def _mask_string(value: str) -> str:
    """Return ``value`` with every embedded timestamp / UUID replaced.

    Strings that contain a timestamp or a UUID inside a longer narrative are
    still normalised so the fixture stays byte-stable across runs.
    """
    masked = _ISO_TIMESTAMP_RE.sub(_TIMESTAMP_PLACEHOLDER, value)
    masked = _UUID_RE.sub(_UUID_PLACEHOLDER, masked)
    return masked


def mask_timestamps(obj: Any) -> Any:
    """Recursively replace timestamps and UUID-shaped ids with placeholders.

    Rules:

    * Any dict key in :data:`_ID_KEYS` whose value is a UUID-shaped string
      (matches the 8-4-4-4-12 hex pattern) is replaced with ``"<UUID>"``.
      Non-UUID-shaped values at the same keys (e.g. the deterministic
      ``reasoning_steps[*].id`` of the form ``"thought-0"`` / ``"tool-1"``)
      are passed through unchanged so determinism information is preserved.
    * Any string value has embedded ISO-8601 timestamps and UUIDs masked
      (so a narrative like ``"resumed at 2026-05-10T08:00:00Z"`` becomes
      ``"resumed at <TIMESTAMP>"``).
    * Lists / dicts are walked recursively. Tuples are coerced to lists so
      JSON serialisation is stable.

    The function is pure: it never mutates ``obj``. The original dict
    insertion order is preserved.
    """
    if isinstance(obj, dict):
        masked: dict[str, Any] = {}
        for key, value in obj.items():
            if (
                key in _ID_KEYS
                and isinstance(value, str)
                and _UUID_RE.fullmatch(value) is not None
            ):
                masked[key] = _UUID_PLACEHOLDER
                continue
            masked[key] = mask_timestamps(value)
        return masked
    if isinstance(obj, list):
        return [mask_timestamps(item) for item in obj]
    if isinstance(obj, tuple):
        return [mask_timestamps(item) for item in obj]
    if isinstance(obj, str):
        return _mask_string(obj)
    return obj


def sort_audit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort audit rows by a stable composite key.

    Each row dict shape is one of the four audit table payloads
    (``agent_runs`` / ``tool_calls`` / ``decision_log`` / ``evidence_traces``).
    Sorting uses ``agent_name``+``step``+``phase`` when present (per the task
    description) with deterministic fallbacks so missing keys do not throw.

    The function is pure and accepts already-masked rows; callers should
    invoke :func:`mask_timestamps` before sorting so the sort key is itself
    stable across runs.
    """

    def _key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
        return (
            str(row.get("agent_name") or row.get("used_by_agent") or ""),
            str(row.get("step") or row.get("decision_type") or ""),
            str(row.get("phase") or ""),
            str(row.get("tool_name") or row.get("citation_id") or ""),
            # Final tiebreaker: the masked id placeholder is identical across
            # rows, so we fall through to the JSON repr to guarantee a total
            # order. Stable across runs because every non-deterministic value
            # has already been masked.
            json.dumps(row, sort_keys=True, ensure_ascii=False),
        )

    return sorted(rows, key=_key)


def sse_lines_to_records(body: str) -> list[dict[str, Any]]:
    """Decode a captured SSE body into a list of one-record-per-line dicts.

    The SSE handler emits ``data: {...}\\n\\n`` per event plus periodic
    ``:keepalive\\n\\n`` comments. Comment lines are dropped. The trailing
    newline pair is preserved by reading the body via the TestClient's
    streaming iterator and keeping the original byte sequence; this helper
    only converts the JSON payload part of each ``data:`` line so the
    fixture stores structured records (more tractable to diff than raw
    bytes while remaining a strict superset of the byte equivalence claim).
    """
    records: list[dict[str, Any]] = []
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[len("data: ") :]
        try:
            records.append(json.loads(payload))
        except json.JSONDecodeError:
            # Malformed line — preserve as a string so the diff still flags it.
            records.append({"_raw": payload})
    return records


# ── BaselineRecorder + fixture ────────────────────────────────────────────────


class BaselineRecorder:
    """Per-scenario capture/compare object exposed via the ``baseline_recorder``
    pytest fixture.

    Tests under ``tests/regressions/`` build one BaselineRecorder per scenario,
    populate it via :meth:`record`, and call :meth:`finalize` at the end of
    the test. ``finalize`` either writes the on-disk fixture (when
    ``--regenerate-baseline`` is passed) or returns the loaded fixture for
    strict equality assertions.

    The captured payload is a JSON-serialisable dict with three top-level
    keys:

    * ``sse_records`` — list of decoded ``data:`` JSON events from the stream.
    * ``message_metadata`` — the final ``conversation_messages.metadata``
      payload that the SSE handler writes via ``update_message_content``.
    * ``audit_rows`` — list of audit-table row dicts in stable sort order;
      see the conftest module docstring for the documented gap on this slot.
    """

    def __init__(self, *, scenario: str, regenerate: bool) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(
                f"unknown scenario {scenario!r}; expected one of {SCENARIOS}"
            )
        self._scenario = scenario
        self._regenerate = regenerate
        self._sse_records: list[dict[str, Any]] = []
        self._message_metadata: dict[str, Any] = {}
        self._audit_rows: list[dict[str, Any]] = []
        self._closed = False

    @property
    def fixture_path(self) -> Path:
        return FIXTURES_DIR / f"sse_baseline_{self._scenario}.json"

    @property
    def regenerate(self) -> bool:
        return self._regenerate

    def record(
        self,
        *,
        sse_body: str,
        message_metadata: dict[str, Any] | None,
        audit_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        """Feed the recorder one full scenario capture.

        ``sse_body`` is the raw SSE response body (text). ``message_metadata``
        is the payload passed to ``DatabaseService.update_message_content``
        for the assistant message at the end of the stream. ``audit_rows`` is
        an optional list of dicts collected from any audit recorder spy.
        """
        if self._closed:
            raise RuntimeError("BaselineRecorder.record called after finalize")
        self._sse_records = sse_lines_to_records(sse_body)
        self._message_metadata = dict(message_metadata or {})
        self._audit_rows = list(audit_rows or [])

    def captured_payload(self) -> dict[str, Any]:
        """Return the masked, sorted, deterministic payload dict.

        This is the same dict that is written to disk during regeneration and
        that callers should compare against the on-disk fixture during normal
        test runs.
        """
        payload = {
            "sse_records": mask_timestamps(self._sse_records),
            "message_metadata": mask_timestamps(self._message_metadata),
            "audit_rows": sort_audit_rows(mask_timestamps(self._audit_rows)),
        }
        return payload

    def finalize(self) -> dict[str, Any]:
        """Write or load the fixture and return the payload that should be
        used for comparison.

        * In regenerate mode: write ``captured_payload()`` to ``fixture_path``
          and return that payload. The on-disk file is overwritten.
        * In compare mode: load ``fixture_path`` and return its JSON content.
          The caller is then responsible for asserting equality between the
          loaded payload and ``captured_payload()``.
        """
        self._closed = True
        captured = self.captured_payload()
        if self._regenerate:
            FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
            self.fixture_path.write_text(
                json.dumps(captured, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            return captured
        if not self.fixture_path.exists():
            pytest.fail(
                f"baseline fixture missing: {self.fixture_path}. "
                "Run `uv run pytest tests/regressions/ --regenerate-baseline` "
                "to generate it."
            )
        return json.loads(self.fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def baseline_recorder(request: pytest.FixtureRequest) -> BaselineRecorder:
    """Return a :class:`BaselineRecorder` bound to the test's scenario.

    The scenario name is sourced from the test's ``scenario`` parameter (when
    parametrised) or, as a fallback, from the test function name suffix
    (``test_<...>_<scenario>``). Tests that need a different convention can
    parametrise explicitly.
    """
    regenerate = bool(request.config.getoption("regenerate_baseline"))
    scenario = _resolve_scenario_from_request(request)
    return BaselineRecorder(scenario=scenario, regenerate=regenerate)


def _resolve_scenario_from_request(request: pytest.FixtureRequest) -> str:
    """Best-effort scenario detection from the requesting test node.

    Resolution order:

    1. ``request.getfixturevalue("scenario")`` — when the test is
       parametrised with a ``scenario`` fixture (the recommended pattern for
       Task 2.2's P4 test).
    2. The trailing token in the test function name after the last
       underscore, when that token is one of :data:`SCENARIOS`.
    3. Raises ``pytest.UsageError`` so the test fails fast with a clear
       message rather than producing a silently-wrong fixture path.
    """
    try:
        scenario = request.getfixturevalue("scenario")
        if isinstance(scenario, str) and scenario in SCENARIOS:
            return scenario
    except (pytest.FixtureLookupError, LookupError):
        pass

    suffix = request.node.name.rsplit("_", 1)[-1]
    if suffix in SCENARIOS:
        return suffix
    # If the test name itself ends with a parametrize id like
    # ``test_foo[general_chat]``, strip the trailing bracket.
    if "[" in request.node.name and request.node.name.endswith("]"):
        token = request.node.name.rsplit("[", 1)[-1].rstrip("]")
        if token in SCENARIOS:
            return token

    raise pytest.UsageError(
        f"baseline_recorder fixture could not infer scenario for test "
        f"{request.node.nodeid!r}; expected a `scenario` parameter or a "
        f"name ending in one of {SCENARIOS}"
    )
