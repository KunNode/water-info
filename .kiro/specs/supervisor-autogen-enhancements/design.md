# Design Document

## Overview

This design extends the existing `water-info-ai` LangGraph supervisor with 5 incremental, independently-toggled capabilities (OpenTelemetry observability, runtime HITL, agent contracts, dynamic topology, persisted task resume). The unifying theme is *additive, instrumented, surgical*: every new behavior hooks into a small number of existing extension points instead of rewriting the orchestrator.

Three shared design choices run through every requirement:

1. **Feature flags as the only switch.** Each enhancement is gated by an env-driven boolean (`OTEL_ENABLED`, `HITL_ENABLED`, `AGENT_CONTRACTS_ENABLED`, `DYNAMIC_TOPOLOGY_ENABLED`, `LANGGRAPH_POSTGRES_ENABLED`). Flags are orthogonal — any subset must produce a service that boots, answers `/health`, and serves `/api/v1/flood/query` correctly. With every flag off the runtime is byte-for-byte identical to the version that exists today.
2. **Two extension points, no graph rewrites.** All five features land inside `audited_agent` (in `app/platform/agent_audit.py`) and `supervisor_node` (in `app/agents/supervisor.py`). The static `StateGraph` built by `build_flood_response_graph()` keeps the same nodes and edges; conditional routing already in place is what we exploit. No runtime `graph.compile()`. No new top-level node added beyond the existing `__interrupt__` LangGraph sentinel route.
3. **Additive state changes only.** `FloodGraphState` keeps its current keys, types, and `Annotated[..., operator.add]` reducers. New fields go *under* existing dicts: `routing_decision.topology_profile`, `routing_decision.overrides.skipped`, `human_review.*`. Audit tables (`agent_runs`, `tool_calls`, `decision_log`, `evidence_traces`) keep their schemas; new rows reuse existing columns. Only one new table is introduced (`pending_approvals`) and only because HITL needs cross-restart durability that LangGraph's checkpointer alone cannot provide.

Read together, the request lifecycle becomes: HTTP route → SSE handler → graph stream → `audited_agent` (OTel span open, contract input check, body run, contract output check, audit rows write, OTel span close, checkpoint persist) → `supervisor_node` (intent inference, topology profile selection, route decision, optional HITL interrupt). The HTTP layer adds one new POST (`/approvals/{id}`) and two new endpoints under `/sessions/{id}` (`/checkpoints` GET, `/resume` POST). Everything else is internal.

The result is a 5-flag matrix where each flag delivers one capability and where the off-state is a strict no-op against the current contract surface.

## Architecture

### Module placement

| Concern | New file | Existing file extended | Notes |
|---|---|---|---|
| OTel bootstrap, no-op fallback, span helpers | `app/observability/otel.py` | — | One module owns tracer init, header injection, helpers. `get_tracer()` returns a no-op tracer when flag off. |
| OTel instrumentation in nodes | — | `app/platform/agent_audit.py:audited_agent` | Wraps existing recorder calls; opens `agent.<name>` span around the existing try/except. |
| OTel instrumentation in supervisor | — | `app/agents/supervisor.py:supervisor_node` | Adds `routing_decision` span event before return. |
| OTel instrumentation in LLM | — | `app/services/llm.py:OpenAICompatibleLLM.ainvoke` | Wraps the `httpx.post` in a `llm.invoke` child span. |
| Agent contracts | `app/agents/_contract.py` | `app/platform/agent_audit.py` | Contract registry + 9 concrete contracts; validation hook inside `audited_agent`. |
| Topology profiles | `app/agents/_topology.py` | `app/agents/supervisor.py` | Profile registry, deterministic selection, decision overrides recorded on `routing_decision`. |
| HITL routing | — | `app/agents/supervisor.py` | Sets `next_agent="__interrupt__"`; SSE handler in `app/main.py` recognizes the sentinel and emits `approval_required`. |
| HITL persistence | `app/platform/approvals.py` | `app/platform/human_in_the_loop.py` | Thin DAO over `pending_approvals`; CAS update; existing in-memory gateway becomes a fallback for tests. |
| HITL HTTP route | — | `app/main.py` | New `POST /api/v1/flood/approvals/{approval_id}` route. |
| Resume endpoints | — | `app/main.py` | `GET /api/v1/flood/sessions/{id}/checkpoints`, `POST /api/v1/flood/sessions/{id}/resume`. |
| Per-node checkpoint | — | `app/platform/agent_audit.py` | Calls existing AsyncPostgresSaver explicitly only when LangGraph would not naturally checkpoint here; no separate writer. |

### Request lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI as app/main.py
    participant Graph as flood_response_graph
    participant Audit as audited_agent
    participant Sup as supervisor_node
    participant Topo as _topology
    participant Contract as _contract
    participant OTel as observability/otel
    participant Saver as AsyncPostgresSaver
    participant DB as pending_approvals + audit tables

    Client->>FastAPI: POST /flood/query/stream
    FastAPI->>OTel: start root span (if OTEL_ENABLED)
    FastAPI->>Graph: astream(state, thread_id=session_id)
    Graph->>Audit: enter node N
    Audit->>OTel: open agent.<N> span
    Audit->>Contract: validate input_model (if AGENT_CONTRACTS_ENABLED)
    alt input invalid
        Contract-->>Audit: ValidationError
        Audit->>DB: agent_runs(failed, contract_input_invalid: ...)
        Audit-->>Graph: route __end__
    else input ok
        Audit->>Audit: run wrapped node body
        Audit->>Contract: validate output_model
        alt output invalid
            Contract-->>Audit: ValidationError
            Audit->>DB: agent_runs(failed, contract_output_invalid: ...)
            Audit-->>Graph: route __end__
        else output ok
            Audit->>DB: agent_runs(completed) + tool_calls + evidence_traces
            Audit->>Saver: persist checkpoint (if LANGGRAPH_POSTGRES_ENABLED)
            Audit->>OTel: close agent.<N> span (OK)
        end
    end
    Audit-->>Graph: state update
    Graph->>Sup: enter supervisor
    Sup->>Topo: select TopologyProfile (if DYNAMIC_TOPOLOGY_ENABLED)
    Topo-->>Sup: profile (priority + lex tiebreak + default fallback)
    Sup->>Sup: enforce skipped_agents / required_agents on next_agent
    alt safety_level == CRITICAL and HITL_ENABLED
        Sup-->>Graph: next_agent = "__interrupt__"
        Graph->>DB: insert pending_approvals(status=pending)
        Graph->>Saver: persist checkpoint
        Graph-->>FastAPI: stream emits approval_required event
        FastAPI-->>Client: SSE approval_required + close stream
        Client->>FastAPI: POST /approvals/{id} {decision}
        FastAPI->>DB: CAS pending → approved/rejected/modified
        FastAPI->>Graph: resume from checkpoint with override_next_agent
    else
        Sup-->>Graph: next_agent (normal route)
    end
    Graph-->>FastAPI: final_response
    FastAPI->>OTel: close root span; inject X-Trace-Id header
    FastAPI-->>Client: response
```

The diagram covers all five requirements end-to-end. It also makes the orthogonality concrete: every dotted-rectangle activity is gated on its own flag, and the path with all flags off is exactly `Audit → run body → audit rows → Sup → next_agent`, which is what the codebase does today.

### Why not a runtime-recompiled StateGraph

For dynamic topology we considered rebuilding `StateGraph` per-request based on the topology profile. We rejected it because (a) `build_flood_response_graph()` already contains every conditional edge we need, (b) recompiling per request changes the LangGraph thread/checkpoint identity model and breaks resume, and (c) profile enforcement is a routing decision, not a structural one — which is exactly what `supervisor_node` already does for the deterministic vs LLM router. Profile enforcement therefore lives next to the existing `_guard_model_route` in `supervisor.py`.

### Why a separate `pending_approvals` table

LangGraph's AsyncPostgresSaver checkpoints the *graph state* but not human-decision rows; `decision_log` is append-only audit; `agent_runs` only records executions. None of those provides the (a) UUID-keyed lookup, (b) atomic CAS state machine `pending → {approved,rejected,modified}`, and (c) cross-restart durability that Requirement 2 requires. The new table is the smallest possible addition: 6 columns, one CAS update, one read.

## Components and Interfaces

### 1. OpenTelemetry helpers (`app/observability/otel.py`)

```python
# Public surface
def init_tracer_provider() -> None: ...
    # Idempotent. If OTEL_ENABLED=false, installs nothing and returns.
    # If init raises or exceeds 5 s, installs a no-op TracerProvider, logs WARN once.

def get_tracer() -> opentelemetry.trace.Tracer: ...
    # Always callable. Returns the global tracer (real or no-op).

def current_trace_id_hex() -> str | None: ...
    # 32-char lowercase hex, or None when no active span.

class agent_span(ContextManager): ...
    # `with agent_span(agent_name, session_id, agent_run_id, iteration) as span:`
    # On enter: opens `agent.<name>` with attributes. On exit:
    #   - exc is None: status OK, sets duration_ms.
    #   - exc raised: records exception, sets error_message (truncated 1024),
    #     status ERROR, then re-raises.

def record_routing_decision(span, decision: dict) -> None: ...
    # Adds a span event named "routing_decision" with the 4 attributes from AC 1.6,
    # truncating reasoning to 2048 chars.

class llm_span(ContextManager): ...
    # `with llm_span(model, temperature) as span:` — wraps an LLM HTTP call,
    # attaches prompt_tokens / completion_tokens / duration_ms after exit.

class tool_span(ContextManager): ...
    # `with tool_span(tool_name) as span:` — for tool.<name> child spans.
    # Attributes: success, latency_ms, error_message (only on failure).
```

Span exporter is `OTLPSpanExporter` over gRPC, batched by `BatchSpanProcessor` with a 100 ms `max_export_timeout_millis` cap so a stalled collector cannot block a node for longer than the AC 1.14 budget.

### 2. Trace ID middleware

The FastAPI app gets one middleware in `app/main.py`:

```python
@app.middleware("http")
async def trace_id_middleware(request, call_next):
    if request.url.path.startswith("/api/v1/flood/query"):
        with get_tracer().start_as_current_span("http.request") as span:
            response = await call_next(request)
            tid = current_trace_id_hex()
            if tid:
                response.headers["X-Trace-Id"] = tid
            return response
    return await call_next(request)
```

When `OTEL_ENABLED=false` the no-op tracer returns no span context, `current_trace_id_hex()` returns `None`, and the header is omitted (AC 1.12 by construction).

### 3. AgentContract (`app/agents/_contract.py`)

```python
from pydantic import BaseModel

class AgentContract:
    agent_name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]

# Module-level registry
_REGISTRY: dict[str, AgentContract] = {}

def register(contract: AgentContract) -> None: ...
def get_contract(agent_name: str) -> AgentContract | None: ...
def all_contracts() -> dict[str, AgentContract]: ...
```

Per-agent files (one per agent in scope) declare the input/output Pydantic models and call `register(...)` at import time. Concrete examples:

```python
# app/agents/contracts/risk_assessor.py
class RiskAssessorIn(BaseModel):
    session_id: str
    data_summary: str
    overview_data: dict | None = None
    weather_forecast: dict | None = None
    answer_policy: dict | None = None

class RiskAssessorOut(BaseModel):
    risk_assessment: dict          # serialized RiskAssessment
    execution_traces: list[dict] = []

register(AgentContract(
    agent_name="risk_assessor",
    input_model=RiskAssessorIn,
    output_model=RiskAssessorOut,
))
```

Validation is integrated into `audited_agent`:

```python
async def wrapped(state):
    contract = get_contract(agent_name) if settings.agent_contracts_enabled else None
    if contract:
        try:
            contract.input_model.model_validate(_slice_state(state, contract.input_model))
        except ValidationError as e:
            await recorder.record_agent_run(...status="failed",
                error_message=f"contract_input_invalid: {_format_errors(e)}")
            return {"next_agent": "__end__"}
    update = await node(state)
    if contract:
        try:
            contract.output_model.model_validate(update)
        except ValidationError as e:
            await recorder.record_agent_run(...status="failed",
                error_message=f"contract_output_invalid: {_format_errors(e)}")
            return {"next_agent": "__end__"}
    return update

def _format_errors(e: ValidationError) -> str:
    # Returns "field_a=missing,field_b=string_type", deterministic ordering by location.
    parts = sorted(f"{'.'.join(map(str, err['loc']))}={err['type']}" for err in e.errors())
    return ",".join(parts)
```

### 4. TopologyProfile (`app/agents/_topology.py`)

```python
from pydantic import BaseModel, Field, field_validator

class ProfileMatch(BaseModel):
    risk_level: str | None = None
    intent: str | None = None
    safety_level: str | None = None

class TopologyProfile(BaseModel):
    profile_name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    match: ProfileMatch
    required_agents: list[str] = Field(default_factory=list, max_length=16)
    skipped_agents: list[str] = Field(default_factory=list, max_length=16)
    priority: int = Field(ge=0, le=1000)

# Built-in profiles
DEFAULT = TopologyProfile(profile_name="default", match=ProfileMatch(),
                          priority=0)
GENERAL_CHAT_FAST_PATH = TopologyProfile(
    profile_name="general_chat_fast_path",
    match=ProfileMatch(intent="general_chat", risk_level="none"),
    skipped_agents=["data_analyst", "risk_assessor", "plan_generator",
                    "resource_dispatcher", "notification"],
    priority=100,
)
DATA_ONLY_FAST_PATH = TopologyProfile(
    profile_name="data_only_fast_path",
    match=ProfileMatch(intent="overview"),  # selected together with answer_policy.data_only
    skipped_agents=["risk_assessor", "plan_generator", "resource_dispatcher",
                    "notification", "safety_checker", "plan_reviewer"],
    priority=200,
)
CRITICAL_RESPONSE_WITH_REVIEW = TopologyProfile(
    profile_name="critical_response_with_review",
    match=ProfileMatch(safety_level="critical"),
    required_agents=["safety_checker", "plan_reviewer"],
    priority=900,
)

PROFILES: list[TopologyProfile] = [
    DEFAULT, GENERAL_CHAT_FAST_PATH, DATA_ONLY_FAST_PATH, CRITICAL_RESPONSE_WITH_REVIEW,
]

def select_profile(*, intent: str, risk_level: str, safety_level: str,
                   answer_policy: dict) -> TopologyProfile:
    """Highest priority match; lexicographic tiebreak; fallback to `default`."""
```

`select_profile` is pure: deterministic, no I/O, no clock. The supervisor calls it after intent inference. Enforcement happens in the existing `_guard_model_route` chain by treating `skipped_agents` as forbidden routes (overriding even the LLM choice) and by pre-empting `__end__` while any `required_agents` row is missing from `agent_runs`.

`data_only_fast_path` matches via the supervisor checking `answer_policy.data_only is True` before calling `select_profile` — if true, the supervisor passes `intent="overview"` regardless of the LLM-inferred intent; the precedence rule (priority 200 > 100) covers AC 4.10.

### 5. ApprovalToken / pending_approvals DAO (`app/platform/approvals.py`)

```python
from pydantic import BaseModel

class PendingApprovalRow(BaseModel):
    approval_id: str            # UUID v4 string
    session_id: str
    thread_id: str              # equals session_id; kept separate for clarity with LangGraph
    checkpoint_id: str          # the checkpoint we will resume from
    action_type: str            # e.g. "critical_route"
    action_payload: dict        # {proposed_next_agent, safety_level, reasoning}
    status: str                 # "pending" | "approved" | "rejected" | "modified"
    created_at: datetime        # ISO-8601 UTC, ms precision
    resolved_at: datetime | None
    resolution: dict | None     # {decision, override_next_agent?, comment?}

class ApprovalsDAO:
    async def insert_pending(row: PendingApprovalRow) -> None: ...
    async def get(approval_id: str) -> PendingApprovalRow | None: ...
    async def cas_resolve(approval_id: str, *,
                          to_status: Literal["approved","rejected","modified"],
                          resolution: dict) -> bool: ...
        # SQL: UPDATE pending_approvals
        #      SET status=$2, resolved_at=NOW(), resolution=$3
        #      WHERE approval_id=$1 AND status='pending'
        # Returns True if exactly one row was affected.
```

### 6. HITL HTTP route

```python
class ApprovalRequest(BaseModel):
    decision: Literal["approve", "reject", "modify"]
    override_next_agent: str | None = Field(
        default=None,
        pattern=r"^(conversation_assistant|data_analyst|risk_assessor|plan_generator|"
                r"resource_dispatcher|notification|execution_monitor|parallel_dispatch|"
                r"knowledge_retriever|plan_reviewer|safety_checker|__end__)$",
    )
    comment: str | None = None

class ApprovalResponse(BaseModel):
    status: Literal["resumed", "rejected", "modified"]
    run_id: str
    checkpoint_id: str

@app.post("/api/v1/flood/approvals/{approval_id}", response_model=ApprovalResponse)
async def resolve_approval(approval_id: str, body: ApprovalRequest): ...
```

On 404 the response body is `{error_code:"approval_not_found", message: ...}`; on 409 `{error_code:"approval_already_resolved", message: ..., current_status: "<...>"}`.

### 7. Resume endpoints

```python
class CheckpointSummary(BaseModel):
    checkpoint_id: str
    last_completed_agent: str
    created_at: datetime
    current_state_summary: dict   # whitelisted keys only

class ResumeRequest(BaseModel):
    checkpoint_id: str | None = None
    override_next_agent: str | None = Field(default=None, pattern="...")  # same regex

class ResumeResponse(BaseModel):
    status: Literal["resumed"]
    run_id: str
    checkpoint_id: str

@app.get("/api/v1/flood/sessions/{session_id}/checkpoints", response_model=list[CheckpointSummary])
@app.post("/api/v1/flood/sessions/{session_id}/resume", response_model=ResumeResponse)
```

`run_id` is a freshly-allocated UUID stored on the resumed graph state's `agent_run_id` for the first node executed after resume. Idempotency uses the tuple `(session_id, checkpoint_id, override_next_agent, sha1(state_at_checkpoint))`; a second `POST /resume` with the same tuple while the first run has not produced a new checkpoint returns 409.

### 8. Checkpoint metadata

LangGraph's existing checkpoint payload already contains the full `FloodGraphState`. We do not duplicate it. The summary returned by `GET /checkpoints` is built from a server-side projection:

```
last_completed_agent = state.current_agent
current_state_summary = {
    "intent": state.intent,
    "safety_level": state.safety_level,
    "has_data_summary": bool(state.data_summary),
    "has_risk_assessment": state.risk_assessment is not None,
    "has_emergency_plan": state.emergency_plan is not None,
    "has_resource_plan": bool(state.resource_plan),
    "has_notifications": bool(state.notifications),
}
```

This avoids leaking large payloads in the checkpoint listing and keeps the response stable.

## Data Models

### New table: `pending_approvals`

```sql
CREATE TABLE IF NOT EXISTS pending_approvals (
    approval_id      UUID PRIMARY KEY,
    session_id       VARCHAR(64) NOT NULL,
    thread_id        VARCHAR(64) NOT NULL,
    checkpoint_id    VARCHAR(64) NOT NULL,
    action_type      VARCHAR(64) NOT NULL,
    action_payload   JSONB       NOT NULL DEFAULT '{}'::jsonb,
    status           VARCHAR(16) NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','approved','rejected','modified')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at      TIMESTAMPTZ,
    resolution       JSONB
);

CREATE INDEX IF NOT EXISTS idx_pending_approvals_session
    ON pending_approvals(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pending_approvals_status
    ON pending_approvals(status) WHERE status = 'pending';
```

### Migration approach

Flyway migrations live in `water-info-platform/src/main/resources/db/migration/` (per AGENTS.md). Existing slots used: V1, V2, V3, V5, V6 (in `docs/sql/` only — see below), V8, V9, V10, V11, V12. Historical gaps: V4, V7. **The next unused slot is V13**, so the migration will be:

```
water-info-platform/src/main/resources/db/migration/V13__pending_approvals.sql
```

Two architectural notes:

- The platform Flyway pipeline already executes from this directory, so a Java-side V13 file ensures the table exists in every environment that runs `water-info-platform`. The AI service does not need its own DDL bootstrap for this table; it only writes to it.
- This is consistent with V12 (`sensor_online_status`) which is similarly written by adjacent services but owned by the platform's migration history. Reusing the platform Flyway also avoids the dual-source issue we currently have with `V6__platform_kernel_audit_tables.sql` living only under `docs/sql/`.

If during implementation we discover the platform migration cadence is too slow, the fallback is an `ensure_pending_approvals_table()` startup hook in the AI service mirroring `ensure_kb_tables()` — but the Flyway path is preferred and is what this design specifies.

### `FloodGraphState` additions (allowed by Requirement 3.9, 4.12, 2)

`FloodGraphState` keeps every existing key, type, and `Annotated[..., operator.add]` reducer. The only changes are:

- `human_review` (new key, type `dict`, additive only): populated by HITL on reject/modify with `{rejected_reason: str, override_reason: str}`. This is the one new top-level key, justified by Requirement 2 explicitly stating `human_review.rejected_reason` and `human_review.override_reason` (AC 2.6, 2.7).
- Inside the existing `routing_decision` dict (no new top-level key): `topology_profile: str` (Requirement 4.12) and `overrides: {skipped: list[str]}` (Requirement 4.6).
- `pending_approvals` already exists in `FloodGraphState` (line 147 of `state.py`) as `list[dict]`. We reuse it; the per-row schema in the dict will match `PendingApprovalRow.model_dump()` minus the database-only `resolved_at`/`resolution` (those live only in the table).

No other top-level keys are added. `current_agent`, `next_agent`, `iteration`, `routing_decision`, `safety_level`, `human_confirmation_required`, `execution_traces` already cover everything else the 5 requirements need.

### Reasoning-step / SSE payload preservation

The existing functions in `app/main.py` (`_reasoning_steps_from_final_state`, `_tool_calls_from_traces`, `_build_stream_events`, `_event_line`) are the byte-level contract surface for SSE `trace_update` and `conversation_messages.metadata.reasoning_steps`. Requirement 1.10 and 3.8 mean: when their respective flags are off, **none of these functions changes by a single byte**. To make this enforceable rather than aspirational, we add a regression fixture (see Testing Strategy) that captures the JSON output for a representative trace and diffs it byte-for-byte across flag toggles.

## Correctness Properties Pre-work

PBT applicability assessment: this feature has multiple genuine universal properties — flag-off equivalence to baseline (metamorphic), idempotence on approve/resume, deterministic profile selection (confluence), structural invariants on agent/span/agent_run counts, and round-trip on resume. PBT is appropriate; some criteria are integration/example-only and we record them as such.

(Pre-work analysis is captured via the `prework` tool call below.)


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

These 17 properties were derived from the prework analysis above, after consolidating logically redundant criteria. EXAMPLE/INTEGRATION/SMOKE/EDGE_CASE criteria are covered by the targeted unit and integration tests in the Testing Strategy section, not by these properties.

### Property 1: Audited-node span well-formedness

*For any* graph run with N audited node executions and `OTEL_ENABLED=true`, exactly N root-level spans named `agent.<agent_name>` are emitted, each carrying `session_id`, `agent_run_id`, `iteration` attributes; each span is closed with status `OK` and a `duration_ms` attribute when the body returns, or with status `ERROR` and a truncated `error_message` (≤1024 chars) when the body raises (in which case the exception is re-raised to the caller).

**Validates: Requirements 1.3, 1.4, 1.5**

### Property 2: Supervisor and child span structure

*For any* graph run with `OTEL_ENABLED=true`: every supervisor invocation that produces a routing decision attaches a span event named `routing_decision` (with `next_agent`, `intent`, `safety_level`, and `reasoning` truncated to 2048 chars) to its parent agent span; every LLM call inside a node emits exactly one child span named `llm.invoke` carrying `model`, `temperature`, `prompt_tokens`, `completion_tokens` (when reported), and `duration_ms`; every execution_trace with `phase=tool_call` emits exactly one child span named `tool.<tool_name>` carrying `success`, `latency_ms`, and `error_message` (only on failure); every `tool.*` and `llm.*` span has exactly one `agent.*` parent.

**Validates: Requirements 1.6, 1.7, 1.8**

### Property 3: X-Trace-Id header presence

*For any* response from `/api/v1/flood/query` or `/api/v1/flood/query/stream`, the `X-Trace-Id` response header is present if and only if there is an active root span at response time; when present, its value matches the regex `^[0-9a-f]{32}$` (exactly 32 lowercase hexadecimal characters representing the active trace_id).

**Validates: Requirements 1.11, 1.12**

### Property 4: All-flags-off byte-for-byte equivalence

*For any* request payload, when all five feature flags (`OTEL_ENABLED`, `HITL_ENABLED`, `AGENT_CONTRACTS_ENABLED`, `DYNAMIC_TOPOLOGY_ENABLED`, `LANGGRAPH_POSTGRES_ENABLED`) are set to `false`, the resulting SSE `trace_update` event payloads (serialized JSON bytes including field order and whitespace), the `conversation_messages.metadata.reasoning_steps` JSONB structure, the rows written to `agent_runs`, `tool_calls`, `decision_log`, and `evidence_traces` (modulo timestamps), and the supervisor's routing decisions are byte-for-byte equivalent to the corresponding outputs produced by the AI_Service version immediately preceding this feature's implementation; equivalently, toggling any single flag from `false` to `true` and back to `false` on the same input produces identical outputs.

**Validates: Requirements 1.10, 2.10, 3.8, 3.11, 4.13**

### Property 5: Approval CAS state machine

*For any* `approval_id` and *any* sequence of concurrent `POST /api/v1/flood/approvals/{approval_id}` calls with decisions in `{approve, reject, modify}` (and a valid `override_next_agent` when modify): exactly one call observes the row in status `pending` and atomically transitions it to one of `approved`/`rejected`/`modified`, returning HTTP 200 and triggering the resume side-effect (resume to original target for approve; resume to `__end__` with `human_review.rejected_reason` for reject; resume to `override_next_agent` with `human_review.override_reason` for modify); every other concurrent call returns HTTP 409 with `error_code=approval_already_resolved` and `current_status` set to the resolved status; calls referencing a non-existent `approval_id` return HTTP 404 with `error_code=approval_not_found`; on every successful transition exactly one `decision_log` row with `decision_type="human_review"` is appended, with `human_approved=true` for approve and modify, `human_approved=false` for reject; failed and rejected calls leave persisted state unchanged.

**Validates: Requirements 2.1, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9**

### Property 6: Interrupt suppresses downstream execution

*For any* graph run where the supervisor produces a `__interrupt__` route under `HITL_ENABLED=true`: a checkpoint is persisted via AsyncPostgresSaver before the interrupt is reported; no `agent_runs` rows for the proposed downstream agent (or any successor of it) appear in the database for that session until the corresponding `pending_approvals` row transitions out of `pending`; the `pending_approvals` row remains durable across both successful SSE flush and client disconnect.

**Validates: Requirements 2.2, 2.3**

### Property 7: Contract enforcement gates the body

*For any* agent with a registered `AgentContract` and `AGENT_CONTRACTS_ENABLED=true`: when the slice of `FloodGraphState` matching `input_model.model_fields` does not validate, the agent body is not invoked, an `agent_runs` row with `status="failed"` and `error_message` matching the regex `^contract_input_invalid: ([a-zA-Z0-9_.]+=[a-zA-Z0-9_]+)(,[a-zA-Z0-9_.]+=[a-zA-Z0-9_]+)*$` (deterministically sorted by field location) is written, and the graph is routed to `__end__`; when the agent body returns an update dict that does not validate against `output_model`, the update is not merged into state, an `agent_runs` row with `status="failed"` and `error_message` prefixed `contract_output_invalid:` (same shape) is written, and the graph is routed to `__end__`; otherwise (both valid, or no registered contract) execution proceeds identically to the contracts-disabled path.

**Validates: Requirements 3.3, 3.4, 3.5, 3.6, 3.11**

### Property 8: Contract registry static invariants

*For any* agent name `n` registered in the contract registry, `set(_required_context_for_agent(n)) ⊆ AgentContract(n).input_model.model_fields.keys()` and `AgentContract(n).output_model.model_fields.keys() ⊆ set(FloodGraphState.__annotations__.keys())`.

**Validates: Requirements 3.7, 3.10**

### Property 9: Topology profile selection is pure and deterministic

*For any* tuple `(intent, risk_level, safety_level, answer_policy)` and *any* set of registered `TopologyProfile`s with `DYNAMIC_TOPOLOGY_ENABLED=true`: `select_profile(...)` returns the profile with the highest `priority` whose `match` keys all equal the corresponding inferred values (omitted `match` keys are treated as wildcards); when multiple profiles tie on priority, it returns the one whose `profile_name` sorts first by Unicode code point; when no profile matches, it returns the `default` profile; the chosen `profile_name` is written to `state.routing_decision.topology_profile`, and exactly one `Execution_Trace` with `phase="data_query"` and `title == f"拓扑适应: {profile_name}"` is appended to `state.execution_traces` per graph run; `select_profile` itself performs no I/O and reads no clock.

**Validates: Requirements 4.1, 4.3, 4.4, 4.5, 4.12**

### Property 10: Topology profile enforcement

*For any* graph run with `DYNAMIC_TOPOLOGY_ENABLED=true` whose chosen profile is `P`: the set of agent names appearing in `agent_runs` for that session is a subset of (all agents in the static graph) MINUS `P.skipped_agents`; for every name `a` in `P.required_agents`, an `agent_runs` row with `agent_name=a` and `status="completed"` exists before any row with `agent_name="final_response"` for the session; when multiple required agents have not yet run, they are routed to in their declaration order in `P.required_agents`; every name in `P.skipped_agents` appears in `state.routing_decision.overrides.skipped`.

**Validates: Requirements 4.6, 4.7**

### Property 11: Per-node checkpoint and resume trace

*For any* graph run with `LANGGRAPH_POSTGRES_ENABLED=true`: at the time the next audited node begins execution, a checkpoint row exists for the just-completed node (the checkpoint count is monotonically non-decreasing in the number of completed nodes); for every successful resume, exactly one `Execution_Trace` with `phase="data_query"` whose `title` contains the value of `last_completed_agent` from the resumed checkpoint is appended to the resumed run's `state.execution_traces`; the persisted checkpoint payload, when round-tripped through serialization, preserves every key currently in `FloodGraphState` that has a non-default value (`routing_decision`, `skill_quality_results`, `evidence_context`, `risk_assessment`, `emergency_plan`, `resource_plan`, `notifications`, `execution_progress`, plus any others present at checkpoint time).

**Validates: Requirements 5.1, 5.8, 5.9**

### Property 12: Checkpoint listing ordering and cap

*For any* `session_id` and *any* number of persisted checkpoints `M`, `GET /api/v1/flood/sessions/{session_id}/checkpoints` returns a JSON array of length `min(M, 50)` sorted strictly by `created_at` descending; when `POST /resume` is invoked without `checkpoint_id` and `M ≥ 1`, the checkpoint with the maximum `created_at` is selected.

**Validates: Requirements 5.2, 5.4**

### Property 13: Resume routing override

*For any* `POST /api/v1/flood/sessions/{session_id}/resume` with a known `checkpoint_id`: when `override_next_agent` is omitted, the resume continues from the saved `next_agent`; when `override_next_agent` matches the existing `SupervisorDecision.next_agent` regex, the resumed graph state has `next_agent` set to that value before any audited node executes; when `checkpoint_id` is unknown for the session, the response is HTTP 404 and no checkpoint row, `agent_runs` row, or other persisted state is mutated.

**Validates: Requirements 5.5, 5.6**

### Property 14: Resume round-trip equals uninterrupted run

*For any* graph run that reaches `__end__` without interruption with `LANGGRAPH_POSTGRES_ENABLED=true`: persisting after each node and resuming from the last (or any earlier) checkpoint produces a final `FloodGraphState` equivalent (modulo wall-clock timestamps and the explicit resume `Execution_Trace`) to a fresh uninterrupted run on the same input; for an interrupted run resumed from checkpoint `K`, the union of `agent_runs` rows from the original partial run and the resumed run equals the `agent_runs` rows of an uninterrupted run on the same input (modulo timestamps and resume-trace record).

**Validates: Requirements 5.10, plus the round-trip correctness property cited at the end of Requirement 5**

### Property 15: Resume idempotence under identical replay

*For any* `(session_id, checkpoint_id, override_next_agent, state_at_checkpoint)` tuple, the first `POST /resume` call returns HTTP 200 with a fresh `run_id` and triggers a new graph run; any subsequent `POST /resume` call with the same tuple — while the original resumed run is still in progress, or has completed without producing a new checkpoint — returns HTTP 409 and creates no additional `agent_runs` rows for nodes that the original checkpoint already records as completed; idempotency is detected by `(checkpoint_id, sha1(state_at_checkpoint))`.

**Validates: Requirement 5.11**

### Property 16: Resume missing-context error

*For any* `POST /resume` whose `override_next_agent` resolves to an agent with a registered `AgentContract` and whose persisted state at `checkpoint_id` does not satisfy `input_model.model_fields`, the response is HTTP 422 with body `{error_code: "missing_context", missing: [<sorted list of field paths>]}`; no graph run is started; no checkpoint, `agent_runs`, or any other persisted state row is created or modified.

**Validates: Requirement 5 final correctness property (missing_context error condition)**

### Property 17: Resume disabled returns 503

*For any* request to `GET /api/v1/flood/sessions/{session_id}/checkpoints` or `POST /api/v1/flood/sessions/{session_id}/resume` while `LANGGRAPH_POSTGRES_ENABLED=false`, the response is HTTP 503 with a JSON error payload indicating persistence is disabled, and no persisted state is created or modified.

**Validates: Requirement 5.7**

## Error Handling

The matrix below summarizes every documented failure path, how it is detected, and how it is recovered. Each row maps to one or more acceptance criteria and is implemented at the cited code path.

| # | Requirement | Failure | Detection | Recovery | Surface | Code path |
|---|---|---|---|---|---|---|
| E1 | 1.13 | Tracer init raises or exceeds 5 s | `init_tracer_provider()` `try/except` + `asyncio.wait_for` | Install no-op tracer; emit one WARN log entry | Startup completes; subsequent calls return no-op tracer | `app/observability/otel.py:init_tracer_provider` |
| E2 | 1.14 | OTLP collector unreachable / export error | `BatchSpanProcessor` export callback | Drop span; bounded by `max_export_timeout_millis=100` | No effect on caller; debug-level log | `app/observability/otel.py` (exporter config) |
| E3 | 1.5 | Audited node body raises | `audited_agent` `try/except` | Span ERROR + truncated error_message; `agent_runs(failed)` written; exception re-raised | Caller sees the original exception | `app/platform/agent_audit.py:audited_agent` |
| E4 | 2.8 (404) | Unknown approval_id | DAO returns `None` | None | HTTP 404 `{error_code:"approval_not_found"}` | `app/main.py` POST handler |
| E5 | 2.8 (409) | CAS affects 0 rows (already resolved) | `cas_resolve()` return value | None | HTTP 409 `{error_code:"approval_already_resolved", current_status: ...}` | `app/platform/approvals.py:ApprovalsDAO.cas_resolve` + handler |
| E6 | 2.7 (modify with bad override) | `override_next_agent` fails regex | Pydantic `ApprovalRequest` validation | None | HTTP 422 (FastAPI default for ValidationError) | FastAPI route schema |
| E7 | 3.5 / 3.6 | Contract validation error | Pydantic `ValidationError` in `audited_agent` | Skip body / drop merge; write `agent_runs(failed, error_message="contract_{input,output}_invalid: ...")`; route to `__end__` | Graph completes with no malformed output; SSE emits the `__end__` path | `app/platform/agent_audit.py` |
| E8 | 4.14 | `select_profile()` raises | `try/except` in supervisor wrapper | Use `default` profile; one WARN log line identifying failed profile + exception type | Graph continues normally with default routing | `app/agents/supervisor.py` (after `_topology` import) |
| E9 | 5.6 / 5.13 | Unknown or no checkpoints | DAO lookup returns empty | None | HTTP 404 with `error_code=checkpoint_not_found` or `no_checkpoints_for_session` | `app/main.py` resume handler |
| E10 | 5.11 | Duplicate `POST /resume` | `(checkpoint_id, sha1(state))` already seen | None | HTTP 409 `{error_code:"resume_already_in_progress"}` | Resume handler + small idempotency cache (in-memory; Postgres advisory lock optional) |
| E11 | 5.12 | Checkpoint persist raises (AsyncPostgresSaver fails) | `try/except` around the saver call in `audited_agent` | Append one WARN-level Execution_Trace identifying the agent; continue graph | Graph completes; client sees the WARN trace via SSE | `app/platform/agent_audit.py` |
| E12 | 5.14 / 5.16 | Resume override needs fields not in checkpoint | Run `input_model.model_validate(state)` before starting graph | None | HTTP 422 `{error_code:"missing_context", missing: [...]}` | Resume handler (uses `_contract` registry) |
| E13 | 5.7 | Resume endpoints called with flag off | Settings check on entry | None | HTTP 503 `{error_code:"persistence_disabled"}` | Resume handler |
| E14 | 1.9 | Audit recorder DB write transient failure | Existing recorder `try/except` (unchanged) | Log warning; do not block node | Same surface as today | `app/platform/audit_recorder.py` (no new logic) |

The matrix follows the existing repo convention: every error path either logs and continues (best-effort observability/audit failures) or surfaces a structured 4xx/5xx with a stable `error_code`. No new exception type leaks to clients.

## Testing Strategy

### Library and configuration

The AI service already runs `pytest` with `hypothesis` available (see `water-info-ai/.hypothesis/constants/...`). All property-based tests use Hypothesis; example, integration, smoke, and edge-case tests are plain pytest functions.

- **Property test minimum**: 100 examples per property (`@settings(max_examples=100)`).
- **Property test tag** (in a leading docstring): `Feature: supervisor-autogen-enhancements, Property {N}: {one-line property text}`.
- **Determinism**: all property tests use `@settings(deterministic=True, derandomize=True)` so CI runs are reproducible. Concurrent CAS tests use `asyncio.gather` over generated permutations.
- **Mocks**: OTLP exporter is replaced with an in-memory `InMemorySpanExporter` (`opentelemetry.sdk.trace.export.in_memory_span_exporter`). LLM client is mocked via dependency injection. Database tests use the existing test Postgres fixture.

### Mapping properties to tests

Each property in the previous section becomes a single property-based test file/function:

| Property | Test file | Notes |
|---|---|---|
| P1 | `tests/observability/test_pbt_agent_span.py` | InMemorySpanExporter + generated state shapes; covers OK/ERROR branches. |
| P2 | `tests/observability/test_pbt_child_spans.py` | Wraps mocked LLM and synthetic execution_traces. |
| P3 | `tests/observability/test_pbt_trace_id_header.py` | FastAPI `TestClient` with both flag values. |
| P4 | `tests/regressions/test_pbt_all_flags_off_equivalence.py` | Critical regression test. Compares JSON bytes of SSE events and audit-row dicts against a frozen golden fixture. |
| P5 | `tests/hitl/test_pbt_approval_cas.py` | `asyncio.gather` of N concurrent calls; asserts exactly one OK and `N-1` 409s. |
| P6 | `tests/hitl/test_pbt_interrupt_suppression.py` | Asserts no downstream agent_runs until status changes. |
| P7 | `tests/contracts/test_pbt_contract_enforcement.py` | Generates invalid state slices; verifies error_message regex and routing to `__end__`. |
| P8 | `tests/contracts/test_pbt_registry_invariants.py` | Iterates registered contracts; checks subset relations. (Domain is finite — Hypothesis is overkill but used for uniformity.) |
| P9 | `tests/topology/test_pbt_select_profile.py` | Pure-function test; generates profiles and inputs. |
| P10 | `tests/topology/test_pbt_profile_enforcement.py` | End-to-end graph run with synthetic profiles. |
| P11 | `tests/persistence/test_pbt_per_node_checkpoint.py` | Asserts checkpoint count and field round-trip. |
| P12 | `tests/persistence/test_pbt_checkpoint_listing.py` | Generates 0..60 checkpoints; verifies listing. |
| P13 | `tests/persistence/test_pbt_resume_routing.py` | Valid + invalid override generators. |
| P14 | `tests/persistence/test_pbt_resume_round_trip.py` | Compares `agent_runs` after uninterrupted run vs interrupted+resumed run. |
| P15 | `tests/persistence/test_pbt_resume_idempotence.py` | Replays identical request; first 200, second 409. |
| P16 | `tests/persistence/test_pbt_resume_missing_context.py` | Generates incomplete state vs override agent contract. |
| P17 | `tests/persistence/test_pbt_resume_503.py` | Flag-off response. |

### Targeted (non-property) tests

- **Smoke (1 example)**: tracer init success path (1.1), tracer no-op path (1.2 boot smoke, complement to P4), AgentContract module import (3.1), 9 contracts registered (3.2), 4 profiles registered (4.2), `FloodGraphState` annotations golden snapshot (3.9), static graph stability (4.11).
- **Integration**: OTLP unreachable best-effort (1.14, real broken collector), pending_approvals durability across restart (2.11, container restart fixture), audit-row writes regardless of flags (1.9, real Postgres).
- **Examples**: tracer init failure recovery (1.13), profile selection exception fallback (4.14), checkpoint persist failure (5.12), zero checkpoints (5.13), happy-path resume response shape (5.3), each named profile's specific routing (4.8/4.9/4.10) one per profile, SSE stream-vs-disconnect approval row durability (2.3), checkpoint persist failure path (5.12).
- **Edge cases**: empty `comment` defaults to empty string (2.6/2.7), `override_next_agent` regex boundary cases (2.7), `created_at` ISO-8601 ms precision (2.1), 60-checkpoint cap (5.2 boundary).

### Regression fixture for byte-for-byte SSE equivalence

A frozen JSON fixture under `tests/regressions/fixtures/sse_baseline_<scenario>.json` captures, per scenario, the exact `data: ...\n\n` SSE bytes (one record per line), the `conversation_messages.metadata.reasoning_steps` JSON, and the rows written to each audit table (sorted, with timestamps masked). Three scenarios:

1. `general_chat_baseline` — single-turn greeting, only `conversation_assistant`.
2. `data_only_baseline` — overview/data query, `data_analyst → final_response`.
3. `full_workflow_baseline` — `data_analyst → risk_assessor → plan_generator → resource_dispatcher → notification → final_response`.

Property P4's test loads each fixture, runs the graph with all five flags off, captures the same outputs, and asserts byte equality. To regenerate after intentional changes, the fixture is rewritten by running `pytest --regenerate-baseline`. This is the regression net Requirements 1.10 and 3.8 demand.

### What we are NOT testing as properties

- AWS / Postgres / OTLP collector behavior: integration tests with 1–2 examples.
- Spring Boot / Java / Vue admin behavior: out of scope for this feature.
- Performance characteristics (e.g. "100 ms export budget"): asserted as a single example, not a property — hypothesis flakiness on timing tests is not worth the noise.

## Rollout / Feature-Flag Matrix

| # | Flag | Default | Module | What it gates | Depends on | Safe with others off |
|---|---|---|---|---|---|---|
| F1 | `OTEL_ENABLED` | `false` | `app/observability/otel.py` | Tracer init, all spans, X-Trace-Id header | nothing | yes |
| F2 | `AGENT_CONTRACTS_ENABLED` | `false` | `app/agents/_contract.py` + `audited_agent` | Pydantic input/output validation | nothing | yes |
| F3 | `DYNAMIC_TOPOLOGY_ENABLED` | `false` | `app/agents/_topology.py` + supervisor | Profile selection + skipped/required enforcement | nothing | yes |
| F4 | `LANGGRAPH_POSTGRES_ENABLED` | `false` (already exists) | `app/langgraph_persistence.py` + audited_agent | Per-node checkpointing, resume endpoints | Postgres reachable | yes |
| F5 | `HITL_ENABLED` | `false` | supervisor + `app/platform/approvals.py` + main.py | `__interrupt__` route + approval REST | F4 strongly recommended (resume requires checkpoint) | yes when F4 also off — interrupt simply does not fire because pre-feature behavior is preserved |

Orthogonality is the load-bearing claim, established by Property 4: every flag's off-state is a strict no-op against the baseline. The dependency between F5 and F4 is asymmetric — when F5 is on but F4 is off, `__interrupt__` is never reached because no checkpoint can be persisted to resume from; the supervisor's pre-feature `human_confirmation_required=true` flag-set behavior is preserved. We document this as the recommended order to avoid surprising operators.

### Recommended production rollout order

1. **F4 `LANGGRAPH_POSTGRES_ENABLED`** — already shipped; verify checkpoint write rate at baseline traffic before enabling anything else.
2. **F1 `OTEL_ENABLED`** — pure observability, zero behavior change. Verify span volumes in Jaeger and that `X-Trace-Id` headers appear; confirm Property 4 regression fixture still passes in CI.
3. **F2 `AGENT_CONTRACTS_ENABLED`** — light enforcement. The risk is that legacy state shapes fail validation. Roll out in a canary: monitor `agent_runs` rows with `error_message LIKE 'contract_input_invalid:%'`, fix the offending state producer or the contract before turning on for the fleet. Property 7's regression set should be expanded with each finding.
4. **F3 `DYNAMIC_TOPOLOGY_ENABLED`** — changes routing. Enable after F2 so any state-shape issue surfaces as a contract failure rather than a downstream NoneType. Verify the `拓扑适应: <profile_name>` Execution_Trace appears in SSE.
5. **F5 `HITL_ENABLED`** — last, because it interacts with both routing (F3) and persistence (F4) and is the only flag that produces user-visible interruptions. Roll out under a tenant whitelist if your deployment supports it.

### Kill-switch behavior

Flipping any flag back to `false` returns the runtime to its pre-flag behavior on the next graph run. There is no required schema rollback: the new `pending_approvals` table can remain in place — turning F5 off simply stops new rows from being inserted, and any existing pending row can still be resolved via the REST endpoint (the endpoint itself only checks F5 on writes; reads remain available). Audit rows already written are unchanged.

### Phase Completion

This design.md is complete for the design phase. Pending user review before proceeding to the tasks phase.
