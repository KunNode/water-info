# Implementation Plan: supervisor-autogen-enhancements

## Overview

This plan delivers the 5 supervisor enhancements described in `design.md` (OpenTelemetry observability, HITL, agent contracts, dynamic topology, per-node checkpoint+resume) as **incremental, surgical, flag-gated** changes. The order below is the **production rollout order from the design's Rollout / Feature-Flag Matrix**, so each flag's implementation completes before the next one begins. Every flag defaults to `false`; the all-flags-off path is byte-for-byte identical to current behavior, locked in by Property 4 regression fixtures captured as the **second** task.

Surgical-changes constraints (per `AGENTS.md`):
- No graph rewrites; all behavior lands inside `audited_agent`, `supervisor_node`, and `app/main.py`.
- `FloodGraphState` keeps every existing key/type/reducer; only one new top-level key (`human_review`) is added (Requirement 3.9, 4.12, 2 explicit).
- Each leaf task ≤200 LOC of source+test where possible; tests are written first (red), then implementation (green).
- All Hypothesis property tests use `@settings(max_examples=100, deterministic=True, derandomize=True)` and a leading docstring tag `Feature: supervisor-autogen-enhancements, Property {N}: {one-line text}` (per design Testing Strategy).
- **PBT applicability confirmed**: design has a "Correctness Properties" section with 17 properties → property tests are required.

Convention used in this plan:
- `_Requirements: ..._` — acceptance-criteria IDs from `requirements.md`.
- `_Property: P..._` — property numbers from `design.md` "Correctness Properties".
- `_Design: §..._` — section in `design.md` whose interface the task implements.
- Sub-tasks postfixed with `*` are optional test sub-tasks (test-first execution still implements them, but they can be skipped for an MVP build).

## Tasks

### Phase A — Bootstrap (shared scaffolding)

- [ ] 1. Add the four new feature-flag settings (off by default) and confirm `langgraph_postgres_enabled` continues to work
  - [x] 1.1 Extend `app/config.py` `Settings` and `get_settings()` with the four new flags
    - Add fields `otel_enabled`, `agent_contracts_enabled`, `dynamic_topology_enabled`, `hitl_enabled` to the `Settings` model, all defaulting to `False`.
    - Wire each to its `_env_bool(...)` lookup inside `get_settings()` (env keys: `OTEL_ENABLED`, `AGENT_CONTRACTS_ENABLED`, `DYNAMIC_TOPOLOGY_ENABLED`, `HITL_ENABLED`).
    - Add the same four entries (commented, all `false`) to `water-info-ai/.env.example` so operators can see the matrix.
    - Touches: `app/config.py`, `.env.example`. Do NOT touch any feature code yet.
    - _Requirements: 1.2, 2.10, 3.8, 4.13, 5.7 (defaults-off premise)_
    - _Design: §Architecture/Module placement — flag table_

  - [x] 1.2 Smoke test: settings defaults are all `False` and respond to env overrides
    - File: `tests/test_settings_flags.py` (new). 1 example per flag (no Hypothesis needed).
    - Asserts `get_settings()` returns `False` for the 4 new flags when env is unset; flips each to `true` and re-loads.
    - _Requirements: 1.2, 2.10, 3.8, 4.13, 5.7_

- [ ] 2. Capture the byte-for-byte SSE / audit baseline fixtures (Property 4 regression net)
  - [ ] 2.1 Build the baseline-capture pytest plugin and the three frozen fixture files
    - File: `tests/regressions/conftest.py` (new) — adds the `--regenerate-baseline` flag (per design's Regression Fixture section).
    - Files: `tests/regressions/fixtures/sse_baseline_general_chat.json`, `sse_baseline_data_only.json`, `sse_baseline_full_workflow.json` (new) — each captures, per the design, the exact `data: ...\n\n` SSE bytes (one record per line), the `conversation_messages.metadata.reasoning_steps` JSON, and rows written to `agent_runs`/`tool_calls`/`decision_log`/`evidence_traces` (sorted, with timestamps masked).
    - Run capture once with all five flags off to populate the fixtures.
    - _Requirements: 1.10, 2.10, 3.8, 3.11, 4.13_
    - _Property: P4_
    - _Design: §Testing Strategy / Regression fixture for byte-for-byte SSE equivalence_

  - [ ] 2.2 Property test P4: all-flags-off byte-for-byte equivalence
    - File: `tests/regressions/test_pbt_all_flags_off_equivalence.py` (new).
    - Hypothesis tag in docstring: `Feature: supervisor-autogen-enhancements, Property 4: All-flags-off byte-for-byte equivalence`.
    - Generates request payloads matching each of the 3 baseline scenarios (general chat / data only / full workflow); for each, runs the graph with all 5 flags `false` and asserts byte equality against the corresponding fixture.
    - Also runs the metamorphic check: toggling any single flag `false → true → false` on the same input produces identical outputs.
    - _Requirements: 1.10, 2.10, 3.8, 3.11, 4.13_
    - _Property: P4_

- [x] 3. Decision + implement: idempotency cache strategy for `POST /resume`
  - [x] 3.1 Pick the idempotency mechanism for `POST /resume` and document it in the task
    - Decide between (a) in-memory dict on the FastAPI worker, (b) Postgres advisory lock keyed on `sha1(checkpoint_id || state_hash)`, (c) a new `resume_idempotency` table.
    - Default recommendation per `design.md` E10: in-memory dict scoped to the FastAPI worker, with a docstring noting the multi-worker limitation; advisory lock is the upgrade path.
    - Implement in `app/platform/resume_idempotency.py` (new file, ≤80 LOC): a single `ResumeIdempotencyCache` class with `try_acquire(checkpoint_id, state_sha1) -> bool`. No FastAPI wiring yet — the resume handler in Phase F task 22 will use it.
    - _Requirements: 5.11_
    - _Property: P15_
    - _Design: §Error Handling — E10_

### Phase B — F4 `LANGGRAPH_POSTGRES_ENABLED` extensions (per-node checkpointing + resume endpoints)

`langgraph_postgres_enabled` already exists; this phase **only adds** per-node persist, the resume endpoints, the 503/404/422/409 error paths, the missing-context contract pre-check, and the resume idempotency hook. No structural rewrite.

- [x] 4. Decision + implement: confirm Flyway V13 vs AI-service ensure-table fallback
  - [x] 4.1 Add the V13 Flyway migration for `pending_approvals`
    - File: `water-info-platform/src/main/resources/db/migration/V13__pending_approvals.sql` (new) — exactly the DDL from `design.md` §Data Models (table + 2 indexes).
    - Confirm the platform Flyway pipeline picks it up (the AI service does not need its own DDL bootstrap; HITL phase tests will exercise it).
    - Document the fallback in `app/platform/approvals.py` docstring (Phase E task 16): if the platform migration has not yet run, an `ensure_pending_approvals_table()` startup hook mirroring `ensure_kb_tables()` is the documented backup. Do NOT add the hook now — only add it if HITL integration tests fail because of the table not existing.
    - _Requirements: 2.1, 2.5, 2.6, 2.7, 2.11_
    - _Design: §Data Models / Migration approach_

- [ ] 5. Add per-node checkpoint persist inside `audited_agent` and the persist-failure trace
  - [ ] 5.1 Property test P11: per-node checkpoint and resume trace
    - File: `tests/persistence/test_pbt_per_node_checkpoint.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 11: Per-node checkpoint and resume trace`.
    - Generates state shapes; runs synthetic graph; asserts checkpoint count is monotonically non-decreasing in the number of completed nodes; asserts the round-tripped checkpoint preserves every non-default `FloodGraphState` key.
    - _Requirements: 5.1, 5.8, 5.9_
    - _Property: P11_

  - [ ] 5.2 Example test for checkpoint persist failure (E11)
    - File: `tests/persistence/test_checkpoint_persist_failure.py` (new). 1 example.
    - Mocks AsyncPostgresSaver to raise; asserts one WARN-level Execution_Trace identifying the failed agent is appended; asserts graph continues to `__end__`; asserts no partial checkpoint row.
    - _Requirements: 5.12_
    - _Design: §Error Handling — E11_

  - [ ] 5.3 Implement per-node checkpoint persist in `audited_agent`
    - Touches: `app/platform/agent_audit.py` (extend the existing `audited_agent` decorator only).
    - When `settings.langgraph_postgres_enabled and audit succeeded`, call the existing `AsyncPostgresSaver` once, after audit rows are written and before the wrapped function returns.
    - Wrap the saver call in `try/except`; on exception, append one `make_trace(phase="data_query", title=f"⚠️ checkpoint persist failed: {agent_name}")` Execution_Trace and continue.
    - _Requirements: 5.1, 5.12_
    - _Property: P11_

- [ ] 6. Add resume endpoints and the missing-context / 503 / 404 / 409 paths
  - [ ] 6.1 Property test P12: checkpoint listing ordering and cap
    - File: `tests/persistence/test_pbt_checkpoint_listing.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 12: Checkpoint listing ordering and cap`.
    - Generates 0..60 checkpoints; asserts list length `min(M, 50)` and strict descending `created_at`; asserts `POST /resume` without `checkpoint_id` selects the max-`created_at` row.
    - _Requirements: 5.2, 5.4_
    - _Property: P12_

  - [ ] 6.2 Property test P13: resume routing override
    - File: `tests/persistence/test_pbt_resume_routing.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 13: Resume routing override`.
    - Valid + invalid `override_next_agent` generators; asserts unknown checkpoint → HTTP 404 + no state mutation.
    - _Requirements: 5.5, 5.6_
    - _Property: P13_

  - [ ] 6.3 Property test P14: resume round-trip equals uninterrupted run
    - File: `tests/persistence/test_pbt_resume_round_trip.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 14: Resume round-trip equals uninterrupted run`.
    - Compares `agent_runs` rows after uninterrupted run vs interrupted+resumed run, modulo timestamps and the resume trace.
    - _Requirements: 5.10_
    - _Property: P14_

  - [ ] 6.4 Property test P15: resume idempotence under identical replay
    - File: `tests/persistence/test_pbt_resume_idempotence.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 15: Resume idempotence under identical replay`.
    - First call 200 + fresh `run_id`; subsequent identical-tuple call returns 409; no extra `agent_runs` rows for already-completed nodes.
    - _Requirements: 5.11_
    - _Property: P15_

  - [ ] 6.5 Property test P16: resume missing-context error
    - File: `tests/persistence/test_pbt_resume_missing_context.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 16: Resume missing-context error`.
    - Generates incomplete state vs override agent contract; asserts 422 with `{error_code:"missing_context", missing:[<sorted>]}` and no graph run is started.
    - _Requirements: 5 final correctness property_
    - _Property: P16_

  - [ ] 6.6 Property test P17: resume disabled returns 503
    - File: `tests/persistence/test_pbt_resume_503.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 17: Resume disabled returns 503`.
    - With `LANGGRAPH_POSTGRES_ENABLED=false`, both endpoints return 503 with `{error_code:"persistence_disabled"}`.
    - _Requirements: 5.7_
    - _Property: P17_

  - [ ] 6.7 Implement `GET /api/v1/flood/sessions/{session_id}/checkpoints`
    - Touches: `app/main.py`. Add a `CheckpointSummary` Pydantic response model exactly as in `design.md` §Components/7.
    - 503 when `langgraph_postgres_enabled is False`; otherwise project the saved checkpoint payload to the whitelisted summary fields.
    - _Requirements: 5.2, 5.7_
    - _Property: P12_, _P17_

  - [ ] 6.8 Implement `POST /api/v1/flood/sessions/{session_id}/resume`
    - Touches: `app/main.py`. Add `ResumeRequest`/`ResumeResponse` Pydantic models exactly as in `design.md` §Components/7.
    - 503 when flag off; 404 when `checkpoint_id` is unknown or session has zero checkpoints; 422 with `{error_code:"missing_context", missing:[...]}` when `override_next_agent` resolves to an agent with a registered `AgentContract` (Phase D) and persisted state at `checkpoint_id` does not satisfy `input_model.model_fields`; 409 from `ResumeIdempotencyCache.try_acquire(...)` (task 3.1) when the same `(checkpoint_id, sha1(state))` is already in flight; 200 + fresh `run_id` otherwise.
    - On successful resume the resumed run's first audited node emits exactly one `make_trace(phase="data_query", title=f"⏯ resumed from {last_completed_agent}")` Execution_Trace (per AC 5.8).
    - _Requirements: 5.3, 5.5, 5.6, 5.7, 5.8, 5.10, 5.11, 5.13, 5.14_
    - _Property: P13_, _P14_, _P15_, _P16_, _P17_
    - _Design: §Components/7, §Error Handling — E9, E10, E12, E13_

- [ ] 7. Checkpoint — F4 extensions land green
  - Ensure all tests pass, ask the user if questions arise.

### Phase C — F1 `OTEL_ENABLED` (OpenTelemetry observability)

- [ ] 8. Build `app/observability/otel.py` (tracer init + helpers)
  - [ ] 8.1 Property test P1: audited-node span well-formedness
    - File: `tests/observability/test_pbt_agent_span.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 1: Audited-node span well-formedness`.
    - Uses `opentelemetry.sdk.trace.export.in_memory_span_exporter.InMemorySpanExporter`; generates state shapes; covers OK and ERROR branches; asserts span attributes and re-raise.
    - _Requirements: 1.3, 1.4, 1.5_
    - _Property: P1_

  - [ ] 8.2 Property test P3: X-Trace-Id header presence
    - File: `tests/observability/test_pbt_trace_id_header.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 3: X-Trace-Id header presence`.
    - FastAPI `TestClient` with both flag values; asserts header presence iff active root span; value matches `^[0-9a-f]{32}$` when present.
    - _Requirements: 1.11, 1.12_
    - _Property: P3_

  - [ ] 8.3 Smoke + edge tests for tracer init (1.1, 1.2, 1.13, 1.14)
    - File: `tests/observability/test_otel_init.py` (new). Plain pytest.
    - Tracer init success path (1.1); no-op path when `OTEL_ENABLED=false` (1.2); init exception fallback to no-op + single WARN log (1.13); OTLP-unreachable best-effort, max 100 ms wait (1.14).
    - _Requirements: 1.1, 1.2, 1.13, 1.14_
    - _Design: §Error Handling — E1, E2_

  - [ ] 8.4 Implement `app/observability/otel.py`
    - File: `app/observability/otel.py` (new). Public surface exactly as in `design.md` §Components/1: `init_tracer_provider()`, `get_tracer()`, `current_trace_id_hex()`, `agent_span(...)`, `record_routing_decision(...)`, `llm_span(...)`, `tool_span(...)`.
    - Idempotent init; OTLP/gRPC exporter targeting `OTEL_EXPORTER_OTLP_ENDPOINT` (default `http://localhost:4317`); `BatchSpanProcessor(max_export_timeout_millis=100)` so a stalled collector cannot block a node beyond AC 1.14's 100 ms budget; init wrapped in `asyncio.wait_for(..., 5.0)` and `try/except` falling back to a no-op tracer with one WARN log.
    - When flag off: `init_tracer_provider()` returns immediately; `get_tracer()` returns the no-op tracer; helpers do nothing.
    - _Requirements: 1.1, 1.2, 1.13, 1.14_
    - _Property: P1_, _P2_, _P3_
    - _Design: §Components/1_

- [ ] 9. Wire OTel into `audited_agent`, `supervisor_node`, `services/llm.py`, and the trace-id middleware
  - [ ] 9.1 Property test P2: supervisor and child span structure
    - File: `tests/observability/test_pbt_child_spans.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 2: Supervisor and child span structure`.
    - Mocks the LLM client and synthetic execution_traces; asserts (a) one `routing_decision` event per supervisor invocation with the 4 attributes (reasoning truncated to 2048 chars), (b) one `llm.invoke` child span per LLM call, (c) one `tool.<tool_name>` child span per `phase=tool_call` execution_trace, (d) every `tool.*`/`llm.*` has exactly one `agent.*` parent.
    - _Requirements: 1.6, 1.7, 1.8_
    - _Property: P2_

  - [ ] 9.2 Add `agent.<name>` span around the existing audited body
    - Touches: `app/platform/agent_audit.py` only — wrap the existing `try/except` with `with agent_span(agent_name, session_id, agent_run_id, iteration) as span:`.
    - On success: status `OK`, set `duration_ms`. On exception: record exception + truncated `error_message` (≤1024 chars), status `ERROR`, re-raise.
    - Gated on `settings.otel_enabled`; flag off → `agent_span` is the no-op CM and bytes are unchanged (verified by Property 4).
    - _Requirements: 1.3, 1.4, 1.5, 1.9, 1.10_
    - _Property: P1_

  - [ ] 9.3 Add `routing_decision` span event in `supervisor_node`
    - Touches: `app/agents/supervisor.py` only — call `record_routing_decision(span, decision)` after the routing decision is built and before return.
    - _Requirements: 1.6_
    - _Property: P2_

  - [ ] 9.4 Add `llm.invoke` child span around the HTTP call in `OpenAICompatibleLLM.ainvoke`
    - Touches: `app/services/llm.py` only — wrap the existing `httpx.post` in `with llm_span(model, temperature) as span:`; on exit, attach `prompt_tokens` / `completion_tokens` (when reported) and `duration_ms`.
    - _Requirements: 1.7_
    - _Property: P2_

  - [ ] 9.5 Add `tool.<tool_name>` child span emission for every `phase=tool_call` execution_trace
    - Touches: `app/platform/agent_audit.py` only — at the existing point where `tool_calls` rows are written, also emit a `tool_span(tool_name)` with `success`, `latency_ms`, and `error_message` (only on failure).
    - _Requirements: 1.8_
    - _Property: P2_

  - [ ] 9.6 Add the FastAPI trace-id middleware and `X-Trace-Id` response header
    - Touches: `app/main.py` — add the `trace_id_middleware` shown in `design.md` §Components/2, scoped to `/api/v1/flood/query` and `/api/v1/flood/query/stream`.
    - When flag off, the no-op tracer returns no span context, `current_trace_id_hex()` returns `None`, and the header is omitted (AC 1.12 by construction).
    - _Requirements: 1.11, 1.12_
    - _Property: P3_

  - [ ] 9.7 Re-run the Property 4 byte-for-byte regression with `OTEL_ENABLED=false`
    - Verify `tests/regressions/test_pbt_all_flags_off_equivalence.py` (task 2.2) still passes after all OTel wiring is in place.
    - _Requirements: 1.10_
    - _Property: P4_

- [ ] 10. Checkpoint — F1 lands green
  - Ensure all tests pass, ask the user if questions arise.

### Phase D — F2 `AGENT_CONTRACTS_ENABLED` (per-agent input/output Pydantic contracts)

- [ ] 11. Build the `AgentContract` registry
  - [ ] 11.1 Property test P8: contract registry static invariants
    - File: `tests/contracts/test_pbt_registry_invariants.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 8: Contract registry static invariants`.
    - Iterates `all_contracts()`; asserts `set(_required_context_for_agent(n)) ⊆ contract.input_model.model_fields.keys()` and `contract.output_model.model_fields.keys() ⊆ set(FloodGraphState.__annotations__.keys())`.
    - _Requirements: 3.7, 3.10_
    - _Property: P8_

  - [ ] 11.2 Smoke test: `AgentContract` module imports + 9 contracts registered
    - File: `tests/contracts/test_contract_registry.py` (new). 1 example.
    - Asserts the 9 named agents are in `_REGISTRY` after importing each `app/agents/contracts/<agent>.py`.
    - _Requirements: 3.1, 3.2_

  - [ ] 11.3 Implement `app/agents/_contract.py`
    - File: `app/agents/_contract.py` (new) — exactly the public surface in `design.md` §Components/3: `AgentContract` dataclass-style class, module-level `_REGISTRY: dict[str, AgentContract] = {}`, `register(...)`, `get_contract(...)`, `all_contracts()`, plus the `_format_errors(e: ValidationError) -> str` helper (deterministic sort by location).
    - _Requirements: 3.1_
    - _Design: §Components/3_

- [ ] 12. Author the 9 concrete agent contracts
  - [ ] 12.1 `data_analyst` contract
    - File: `app/agents/contracts/data_analyst.py` (new). Define `DataAnalystIn`, `DataAnalystOut`; call `register(...)` at import. Input must be a superset of `_required_context_for_agent("data_analyst")`; output must be a subset of `FloodGraphState` keys.
    - _Requirements: 3.2, 3.7, 3.10_
    - _Property: P8_

  - [ ] 12.2 `risk_assessor` contract
    - File: `app/agents/contracts/risk_assessor.py` (new). Models match `design.md` §Components/3 example.
    - _Requirements: 3.2, 3.7, 3.10_
    - _Property: P8_

  - [ ] 12.3 `plan_generator` contract
    - File: `app/agents/contracts/plan_generator.py` (new).
    - _Requirements: 3.2, 3.7, 3.10_
    - _Property: P8_

  - [ ] 12.4 `resource_dispatcher` contract
    - File: `app/agents/contracts/resource_dispatcher.py` (new).
    - _Requirements: 3.2, 3.7, 3.10_
    - _Property: P8_

  - [ ] 12.5 `notification` contract
    - File: `app/agents/contracts/notification.py` (new).
    - _Requirements: 3.2, 3.7, 3.10_
    - _Property: P8_

  - [ ] 12.6 `execution_monitor` contract
    - File: `app/agents/contracts/execution_monitor.py` (new).
    - _Requirements: 3.2, 3.7, 3.10_
    - _Property: P8_

  - [ ] 12.7 `knowledge_retriever` contract
    - File: `app/agents/contracts/knowledge_retriever.py` (new).
    - _Requirements: 3.2, 3.7, 3.10_
    - _Property: P8_

  - [ ] 12.8 `plan_reviewer` contract
    - File: `app/agents/contracts/plan_reviewer.py` (new).
    - _Requirements: 3.2, 3.7, 3.10_
    - _Property: P8_

  - [ ] 12.9 `safety_checker` contract
    - File: `app/agents/contracts/safety_checker.py` (new).
    - _Requirements: 3.2, 3.7, 3.10_
    - _Property: P8_

  - [ ] 12.10 Smoke test: `FloodGraphState` annotations golden snapshot
    - File: `tests/contracts/test_state_annotations_snapshot.py` (new). 1 example.
    - Asserts `set(FloodGraphState.__annotations__.keys())` matches a frozen golden set; this is the safety net for AC 3.9 (state shape stability).
    - _Requirements: 3.9_

- [ ] 13. Wire contract validation into `audited_agent`
  - [ ] 13.1 Property test P7: contract enforcement gates the body
    - File: `tests/contracts/test_pbt_contract_enforcement.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 7: Contract enforcement gates the body`.
    - Generates invalid state slices; verifies (a) body not invoked on bad input, (b) `agent_runs(failed)` row with `error_message` matching `^contract_input_invalid: ([a-zA-Z0-9_.]+=[a-zA-Z0-9_]+)(,[a-zA-Z0-9_.]+=[a-zA-Z0-9_]+)*$`, (c) `__end__` route, (d) symmetric output-validation case, (e) flag-off path identical to before.
    - _Requirements: 3.3, 3.4, 3.5, 3.6, 3.11_
    - _Property: P7_

  - [ ] 13.2 Add the input-validation gate inside `audited_agent`
    - Touches: `app/platform/agent_audit.py` only — wrap the existing body call with the snippet from `design.md` §Components/3.
    - When `settings.agent_contracts_enabled` is `False` OR `get_contract(agent_name) is None`: skip validation entirely (AC 3.8, 3.11).
    - _Requirements: 3.3, 3.5, 3.11_
    - _Property: P7_
    - _Design: §Error Handling — E7_

  - [ ] 13.3 Add the output-validation gate inside `audited_agent`
    - Touches: `app/platform/agent_audit.py` only — same wrapping snippet.
    - On `ValidationError`: record `agent_runs(failed, error_message="contract_output_invalid: ...")`, do NOT merge update into state, route to `__end__`.
    - _Requirements: 3.4, 3.6_
    - _Property: P7_
    - _Design: §Error Handling — E7_

  - [ ] 13.4 Re-run the Property 4 byte-for-byte regression with `AGENT_CONTRACTS_ENABLED=false`
    - Verify `tests/regressions/test_pbt_all_flags_off_equivalence.py` still passes.
    - _Requirements: 3.8, 3.11_
    - _Property: P4_

- [ ] 14. Checkpoint — F2 lands green
  - Ensure all tests pass, ask the user if questions arise.

### Phase E — F3 `DYNAMIC_TOPOLOGY_ENABLED` (topology profiles)

- [ ] 15. Build `app/agents/_topology.py` and the supervisor enforcement
  - [ ] 15.1 Decision + implement: `data_only_fast_path` selection mechanism
    - Decide between (a) supervisor checks `answer_policy.data_only is True` and overrides `intent="overview"` before calling `select_profile` (priority 200 wins over `general_chat_fast_path`'s 100), or (b) add `data_only` to `ProfileMatch`.
    - Default per `design.md` §Components/4: option (a). Document the choice as a comment above `select_profile`.
    - _Requirements: 4.10_
    - _Property: P9_

  - [ ] 15.2 Property test P9: topology profile selection is pure and deterministic
    - File: `tests/topology/test_pbt_select_profile.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 9: Topology profile selection is pure and deterministic`.
    - Generates `(intent, risk_level, safety_level, answer_policy)` tuples and registered profile sets; asserts highest-priority match wins, lex tiebreak, default fallback, no I/O / no clock; asserts `state.routing_decision.topology_profile` is written and exactly one `phase="data_query"` Execution_Trace with `title == f"拓扑适应: {profile_name}"` is appended per graph run.
    - _Requirements: 4.1, 4.3, 4.4, 4.5, 4.12_
    - _Property: P9_

  - [ ] 15.3 Smoke tests: 4 named profiles registered + per-profile routing examples
    - File: `tests/topology/test_topology_profiles.py` (new). 1 example per case.
    - 4 built-in profiles registered (4.2); `general_chat_fast_path` routes `conversation_assistant → final_response` only (4.9); `data_only_fast_path` routes through `data_analyst → final_response` only (4.10); `critical_response_with_review` injects `safety_checker` first then `plan_reviewer` after `plan_generator` and before `resource_dispatcher` (4.8); profile-selection-exception fallback to `default` with one WARN log (4.14); static graph stability — `build_flood_response_graph()` includes all node definitions unchanged (4.11).
    - _Requirements: 4.2, 4.8, 4.9, 4.10, 4.11, 4.14_
    - _Design: §Error Handling — E8_

  - [ ] 15.4 Implement `app/agents/_topology.py`
    - File: `app/agents/_topology.py` (new) — exactly the public surface in `design.md` §Components/4: `ProfileMatch`, `TopologyProfile`, `DEFAULT`, `GENERAL_CHAT_FAST_PATH`, `DATA_ONLY_FAST_PATH`, `CRITICAL_RESPONSE_WITH_REVIEW`, `PROFILES: list[TopologyProfile]`, `select_profile(...)`. Pure: deterministic, no I/O, no clock.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
    - _Property: P9_
    - _Design: §Components/4_

- [ ] 16. Wire the supervisor to enforce `skipped_agents` / `required_agents` and emit the topology trace
  - [ ] 16.1 Property test P10: topology profile enforcement
    - File: `tests/topology/test_pbt_profile_enforcement.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 10: Topology profile enforcement`.
    - End-to-end synthetic graph runs; asserts (a) actual agent set ⊆ all-agents − `skipped_agents`, (b) every `required_agents` row exists with `status="completed"` before `final_response`, (c) routing order matches `required_agents` declaration order, (d) every skipped name appears in `state.routing_decision.overrides.skipped`.
    - _Requirements: 4.6, 4.7_
    - _Property: P10_

  - [ ] 16.2 Plug profile selection into `supervisor_node`
    - Touches: `app/agents/supervisor.py` only — after `intent`/`risk_level`/`safety_level` inference and right before the existing `_guard_model_route` chain, call `select_profile(...)` (gated on `settings.dynamic_topology_enabled`), wrapped in `try/except` that falls back to `DEFAULT` with one WARN log per AC 4.14.
    - Write `selected.profile_name` into `state.routing_decision.topology_profile` and append the `拓扑适应: ...` trace via `make_trace` exactly once per run.
    - When flag off: skip selection, do not write `topology_profile`, do not emit the trace (AC 4.13).
    - _Requirements: 4.3, 4.12, 4.13, 4.14_
    - _Property: P9_

  - [ ] 16.3 Enforce `skipped_agents` and `required_agents` in `_guard_model_route`
    - Touches: `app/agents/supervisor.py` only — extend the existing guard to (a) refuse to route to any name in `skipped_agents` (overriding LLM choice), recording it in `state.routing_decision.overrides.skipped`; (b) pre-empt `__end__` while any `required_agents` entry is missing from `agent_runs`, in declaration order.
    - _Requirements: 4.6, 4.7_
    - _Property: P10_

  - [ ] 16.4 Re-run the Property 4 byte-for-byte regression with `DYNAMIC_TOPOLOGY_ENABLED=false`
    - _Requirements: 4.13_
    - _Property: P4_

- [ ] 17. Checkpoint — F3 lands green
  - Ensure all tests pass, ask the user if questions arise.

### Phase F — F5 `HITL_ENABLED` (human-in-the-loop pause/resume)

Depends on F4 (per-node checkpointing must already work). When F5 is on but F4 is off, the pre-feature `human_confirmation_required=true` flag-set behavior is preserved (per `design.md` Rollout Matrix).

- [ ] 18. Add the `human_review` state key (the only new top-level `FloodGraphState` key)
  - [ ] 18.1 Add `human_review` to `app/state.py`
    - Touches: `app/state.py` only — add `human_review: dict` (additive; default `{}`). No other key changes; no other type changes; no reducer changes (AC 3.9, 4.12).
    - _Requirements: 2.6, 2.7, 3.9_
    - _Design: §Data Models / `FloodGraphState` additions_

  - [ ] 18.2 Update the `FloodGraphState` annotations golden snapshot test
    - Update `tests/contracts/test_state_annotations_snapshot.py` (from task 12.10) golden value to include `human_review`. Confirm no other key changed.
    - _Requirements: 3.9_

- [ ] 19. Implement `app/platform/approvals.py` (DAO over `pending_approvals`)
  - [ ] 19.1 Property test P5: approval CAS state machine
    - File: `tests/hitl/test_pbt_approval_cas.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 5: Approval CAS state machine`.
    - `asyncio.gather` of N concurrent `POST /approvals/{id}` calls with mixed decisions; asserts exactly one HTTP 200 and `N-1` 409s; exactly one `decision_log(decision_type="human_review")` row appended per success; `human_approved` true for approve+modify, false for reject; failed/rejected calls leave persisted state unchanged; unknown id → 404.
    - _Requirements: 2.1, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9_
    - _Property: P5_

  - [ ] 19.2 Integration test: `pending_approvals` durability across restart
    - File: `tests/hitl/test_pending_approvals_durability.py` (new). Uses container-restart fixture.
    - _Requirements: 2.11_

  - [ ] 19.3 Implement `ApprovalsDAO`
    - File: `app/platform/approvals.py` (new) — exactly the surface in `design.md` §Components/5: `PendingApprovalRow`, `ApprovalsDAO.insert_pending`, `.get`, `.cas_resolve(...)` returning `True` iff exactly one row was affected.
    - _Requirements: 2.1, 2.5, 2.6, 2.7, 2.11_
    - _Property: P5_
    - _Design: §Components/5, §Error Handling — E5_

- [ ] 20. Wire the `__interrupt__` route into `supervisor_node` and the SSE handler
  - [ ] 20.1 Property test P6: interrupt suppresses downstream execution
    - File: `tests/hitl/test_pbt_interrupt_suppression.py` (new).
    - Hypothesis tag: `Feature: supervisor-autogen-enhancements, Property 6: Interrupt suppresses downstream execution`.
    - Asserts (a) checkpoint persisted before interrupt is reported, (b) no `agent_runs` rows for the proposed downstream agent (or any successor) until the `pending_approvals` row leaves `pending`, (c) `pending_approvals` row durable across SSE flush AND client disconnect.
    - _Requirements: 2.2, 2.3_
    - _Property: P6_

  - [ ] 20.2 Example test: SSE `approval_required` event shape + non-streaming 202
    - File: `tests/hitl/test_approval_required_sse.py` (new). 1 example each.
    - SSE path emits `approval_required` event with `approval_id`, `proposed_next_agent`, `safety_level`, `reasoning`, `action_payload`, then closes (2.3); non-streaming `/api/v1/flood/query` returns HTTP 202 with `{status:"approval_required", approval_id, proposed_next_agent, reasoning}` (2.4).
    - _Requirements: 2.3, 2.4_

  - [ ] 20.3 Add the CRITICAL → `__interrupt__` branch in `supervisor_node`
    - Touches: `app/agents/supervisor.py` only — when `settings.hitl_enabled and safety_level == CRITICAL`: allocate a UUID v4 `approval_id`, insert a `pending_approvals` row via `ApprovalsDAO.insert_pending(...)`, set `next_agent = "__interrupt__"`, append the row to `state.pending_approvals` (existing key, list[dict]). When flag off: preserve the existing `human_confirmation_required=true` behavior (AC 2.10).
    - _Requirements: 2.1, 2.10_
    - _Property: P6_

  - [ ] 20.4 Add the `__interrupt__` SSE branch in `app/main.py`
    - Touches: `app/main.py` only — recognize the sentinel, persist the LangGraph checkpoint via the existing AsyncPostgresSaver, emit one `approval_required` SSE event, close the stream when either the flush completes OR a client disconnect is observed (whichever first). On the non-streaming `/api/v1/flood/query` path, return HTTP 202 with `{status:"approval_required", approval_id, proposed_next_agent, reasoning}`.
    - _Requirements: 2.2, 2.3, 2.4_
    - _Property: P6_

- [ ] 21. Implement `POST /api/v1/flood/approvals/{approval_id}` and resume on resolve
  - [ ] 21.1 Add the approval-resolve route to `app/main.py`
    - Touches: `app/main.py` only — `ApprovalRequest`/`ApprovalResponse` Pydantic models exactly as in `design.md` §Components/6.
    - On approve: CAS pending → approved; on success resume from checkpoint with `human_confirmation_required = false` and no override; on reject: CAS pending → rejected, resume to `__end__` with `state.human_review.rejected_reason = body.comment or ""`; on modify: CAS pending → modified, resume routing to `body.override_next_agent` with `state.human_review.override_reason = body.comment or ""`.
    - 404 → `{error_code:"approval_not_found", message:...}`; 409 → `{error_code:"approval_already_resolved", message:..., current_status:"<...>"}`. CAS-affecting-zero-rows is the 409 trigger.
    - On every successful transition, append exactly one `decision_log` row with `decision_type="human_review"` and `human_approved` true for approve/modify, false for reject.
    - _Requirements: 2.5, 2.6, 2.7, 2.8, 2.9_
    - _Property: P5_
    - _Design: §Components/6, §Error Handling — E4, E5, E6_

  - [ ] 21.2 Re-run the Property 4 byte-for-byte regression with `HITL_ENABLED=false`
    - Verify the all-flags-off path is still byte-for-byte equivalent (AC 2.10 metamorphic).
    - _Requirements: 2.10_
    - _Property: P4_

- [ ] 22. Cross-flag smoke test: every flag toggles independently
  - [ ] 22.1 Add the flag-matrix smoke test
    - File: `tests/test_flag_matrix_smoke.py` (new). For each of the 5 flags: enable that flag alone (the other 4 off) and run a representative request through `/api/v1/flood/query/stream`; assert the request completes and the per-flag observable behavior is present (a span for OTel; a contract `agent_runs(failed)` shape for contracts; the topology trace for topology; a checkpoint row for persistence; an `approval_required` event for HITL with a CRITICAL fixture). Assert turning the flag off restores the byte-for-byte baseline. _Requirements: 1.10, 2.10, 3.8, 4.13, 5.7_
    - _Property: P4_

- [ ] 23. Final checkpoint — full suite green
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Sub-tasks marked with `*` are optional test sub-tasks (tests are still written first per the spec's red→green discipline; the marker only allows skipping for an MVP build).
- Top-level tasks are never marked optional.
- Each leaf task references both the requirement IDs (e.g. `_Requirements: 1.3, 1.4_`) and, where applicable, the property number(s) it locks in (e.g. `_Property: P1_`).
- Property 4 (byte-for-byte regression) is captured **first** (task 2) and re-verified after every phase that touches a flag-on code path (tasks 9.7, 13.4, 16.4, 21.2).
- The 17 PBT files map 1-to-1 with properties P1–P17; their paths follow the design's "Mapping properties to tests" table.
- Phase F depends on Phase B (resume requires checkpointing). All other phases are independent.

## Phase Completion / Verification

When every task above is complete, verify the feature with:

- `cd water-info-ai && uv run pytest tests/ -v` — entire suite passes (existing tests + the 17 new property tests + the targeted unit/integration/smoke tests + the 3 byte-for-byte SSE regression scenarios).
- `cd water-info-ai && uv run ruff check app/ tests/` — clean.
- All 17 properties' Hypothesis tests pass with `@settings(max_examples=100, deterministic=True, derandomize=True)`.
- The byte-for-byte SSE regression fixture (`tests/regressions/fixtures/sse_baseline_*.json`) matches with all 5 flags off across all 3 scenarios (`general_chat_baseline`, `data_only_baseline`, `full_workflow_baseline`).
- The flag-matrix smoke test (task 22.1) demonstrates that each flag (`OTEL_ENABLED`, `AGENT_CONTRACTS_ENABLED`, `DYNAMIC_TOPOLOGY_ENABLED`, `LANGGRAPH_POSTGRES_ENABLED`, `HITL_ENABLED`) can be independently toggled on without breaking the others, matching the recommended production rollout order in `design.md` §Rollout Matrix.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "3.1", "4.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["5.1", "5.2", "6.1", "6.2", "6.3", "6.4", "6.5", "6.6"] },
    { "id": 4, "tasks": ["5.3"] },
    { "id": 5, "tasks": ["6.7", "6.8"] },
    { "id": 6, "tasks": ["8.1", "8.2", "8.3"] },
    { "id": 7, "tasks": ["8.4"] },
    { "id": 8, "tasks": ["9.1"] },
    { "id": 9, "tasks": ["9.2", "9.3", "9.4", "9.5", "9.6"] },
    { "id": 10, "tasks": ["9.7"] },
    { "id": 11, "tasks": ["11.1", "11.2"] },
    { "id": 12, "tasks": ["11.3"] },
    { "id": 13, "tasks": ["12.1", "12.2", "12.3", "12.4", "12.5", "12.6", "12.7", "12.8", "12.9", "12.10"] },
    { "id": 14, "tasks": ["13.1"] },
    { "id": 15, "tasks": ["13.2", "13.3"] },
    { "id": 16, "tasks": ["13.4"] },
    { "id": 17, "tasks": ["15.1", "15.2", "15.3"] },
    { "id": 18, "tasks": ["15.4"] },
    { "id": 19, "tasks": ["16.1"] },
    { "id": 20, "tasks": ["16.2"] },
    { "id": 21, "tasks": ["16.3"] },
    { "id": 22, "tasks": ["16.4"] },
    { "id": 23, "tasks": ["18.1"] },
    { "id": 24, "tasks": ["18.2", "19.1", "19.2"] },
    { "id": 25, "tasks": ["19.3"] },
    { "id": 26, "tasks": ["20.1", "20.2"] },
    { "id": 27, "tasks": ["20.3"] },
    { "id": 28, "tasks": ["20.4"] },
    { "id": 29, "tasks": ["21.1"] },
    { "id": 30, "tasks": ["21.2"] },
    { "id": 31, "tasks": ["22.1"] }
  ]
}
```
