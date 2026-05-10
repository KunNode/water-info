# Implementation Plan: 防汛智能体平台内核 (Flood Agent Platform Kernel)

## Overview

Incremental implementation of the platform kernel across 5 phases, each independently toggleable via feature flags. All work is in the `water-info-ai` Python service. Each phase builds on the previous, with cross-cutting concerns (feature flags, backward compatibility, audit) woven throughout.

## Tasks

- [ ] 1. Foundation: Feature Flags and Platform Package Structure
  - [ ] 1.1 Add feature flag fields to Settings and extend `get_settings()`
    - Add `structured_output_enabled`, `skill_registry_enabled`, `dispatch_state_machine_enabled`, `audit_tables_enabled`, `plan_reviewer_enabled` to `app/config.py` Settings dataclass
    - Add corresponding `os.environ.get()` calls in `get_settings()` with defaults of `False`
    - _Requirements: 15.1, 15.2, 15.3_

  - [ ] 1.2 Create `app/platform/` package with `__init__.py`
    - Create directory `app/platform/` and empty `__init__.py`
    - This package will house all new platform kernel modules
    - _Requirements: 14.4_

  - [ ] 1.3 Extend FloodGraphState with new additive fields
    - Add new fields to `app/state.py` FloodGraphState TypedDict: `agent_run_id`, `routing_decision`, `safety_level`, `human_confirmation_required`, `active_skill_id`, `skill_agent_sequence`, `skill_quality_results`, `compliance_result`, `safety_check_result`, `pending_approvals`, `dispatch_orders`, `metadata_filter`
    - All new fields use `total=False` (already set on TypedDict)
    - Preserve all existing fields unchanged
    - _Requirements: 14.4, 1.4_

  - [ ]* 1.4 Write property test for FloodGraphState backward compatibility
    - **Property 21: FloodGraphState backward compatibility**
    - **Validates: Requirements 14.4**
    - File: `tests/pbt/test_state_compat.py`

  - [ ]* 1.5 Write property test for feature flag bypass behavior
    - **Property 20: Feature flag bypass behavior**
    - **Validates: Requirements 15.2**
    - File: `tests/pbt/test_feature_flags.py`

- [ ] 2. Phase 1: Multi-Agent Platform Layer — Structured Output
  - [ ] 2.1 Create `app/schemas/agent_outputs.py` with Pydantic output models
    - Define `RiskAssessorOutput`, `PlanGeneratorOutput`, `ResourceDispatcherOutput`, `ResourceAllocationOutput`, `ExecutionMonitorOutput` Pydantic BaseModel classes
    - Include field validators (ge, le, gt constraints) as specified in design
    - Create `app/schemas/__init__.py`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ] 2.2 Create `RoutingDecision` model and `SafetyLevel` enum in `app/schemas/routing.py`
    - Define `SafetyLevel` enum (normal, elevated, high, critical)
    - Define `RoutingDecision` Pydantic model with fields: agent_run_id, intent, next_agent, required_context, missing_context, reasoning, safety_level, human_confirmation_required
    - Implement `model_post_init` to auto-set `human_confirmation_required=True` when safety_level is high/critical
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 2.3 Write property tests for routing decision schema and safety level invariant
    - **Property 1: Supervisor routing decision schema completeness**
    - **Property 2: High safety level implies human confirmation**
    - **Property 3: Agent run ID uniqueness**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    - File: `tests/pbt/test_routing_decision.py`

  - [ ] 2.4 Create `app/platform/output_validator.py` with schema registry and validation logic
    - Define `OutputValidationResult` dataclass
    - Implement `validate_agent_output()` async function that validates agent output against registered Pydantic schema
    - On failure: return graceful degradation with raw output and error list
    - Build schema registry mapping agent_name → Pydantic model class
    - _Requirements: 2.5, 2.6_

  - [ ]* 2.5 Write property test for agent output schema conformance
    - **Property 4: Agent output schema conformance**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6**
    - File: `tests/pbt/test_agent_outputs.py`

  - [ ] 2.6 Enhance `supervisor_node` in `app/agents/supervisor.py` for structured routing
    - When `structured_output_enabled` is True, produce a `RoutingDecision` object and write to state
    - Generate `agent_run_id` (UUID v4) and attach to state
    - Preserve existing fallback logic when flag is disabled or LLM routing fails
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 14.3_

  - [ ]* 2.7 Write unit tests for supervisor structured routing and fallback
    - Test structured output generation with mock LLM
    - Test fallback to deterministic routing on LLM failure
    - Test feature flag disabled → existing behavior preserved
    - File: `tests/unit/test_supervisor_fallback.py`
    - _Requirements: 1.6, 15.2_

- [ ] 3. Checkpoint — Phase 1 complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Phase 2: RAG Knowledge Layer
  - [ ] 4.1 Create `MetadataFilter` model and `RetrievalMode` enum in `app/rag/models.py`
    - Add `RetrievalMode` enum (ANSWER, PREFLIGHT_PLAN, PREFLIGHT_RISK, VALIDATION)
    - Add `MetadataFilter` Pydantic model with fields: doc_type, region_code, basin_code, station_id, effective_date, expire_date, authority_level, risk_level_applicable
    - _Requirements: 4.4, 5.1, 5.4_

  - [ ] 4.2 Extend `hybrid_search()` in `app/rag/retriever.py` with metadata pre-filtering
    - Add `metadata_filter: MetadataFilter | None` parameter to `hybrid_search()`
    - Build SQL WHERE clauses for metadata fields before vector similarity
    - Exclude expired documents (expire_date < today) by default
    - Implement progressive filter relaxation on zero results
    - _Requirements: 4.4, 4.5, 5.2, 5.3_

  - [ ]* 4.3 Write property tests for metadata filtering
    - **Property 6: Metadata filter exclusion of expired documents**
    - **Property 7: Metadata enum validation**
    - **Validates: Requirements 5.2, 5.4**
    - File: `tests/pbt/test_rag_metadata.py`

  - [ ] 4.4 Create `app/agents/plan_reviewer.py` — Plan_Reviewer agent
    - Define `ComplianceResult` and `ViolationDetail` Pydantic models
    - Implement `plan_reviewer_node(state)` that retrieves regulatory evidence in validation mode and checks plan compliance
    - Return compliance_result to state; on violation, flag plan for revision
    - Gate behind `plan_reviewer_enabled` feature flag
    - _Requirements: 6.1, 6.3_

  - [ ] 4.5 Create `app/agents/safety_checker.py` — Safety_Checker agent
    - Define `SafetyCheckResult` model and `HIGH_RISK_ACTIONS` set
    - Implement `safety_checker_node(state)` that verifies high-risk actions against safety constraints
    - When `safe_to_proceed=False`, block action and require human approval
    - Gate behind `plan_reviewer_enabled` feature flag
    - _Requirements: 6.2, 6.4_

  - [ ]* 4.6 Write unit tests for Plan_Reviewer and Safety_Checker
    - Test compliance check with mock LLM and mock evidence
    - Test high-risk action detection and blocking
    - Test graceful degradation when LLM unavailable
    - Files: `tests/unit/test_plan_reviewer.py`, `tests/unit/test_safety_checker.py`
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ] 4.7 Integrate Plan_Reviewer and Safety_Checker into LangGraph workflow
    - Add `plan_reviewer` and `safety_checker` nodes to `app/graph.py`
    - Add conditional edges: plan_generator → plan_reviewer (when enabled), safety_checker triggered on high-risk actions
    - Preserve existing routing when flags disabled
    - _Requirements: 4.1, 4.2, 4.3, 6.1, 6.2_

- [ ] 5. Checkpoint — Phase 2 complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Phase 3: Skill Registry Layer
  - [ ] 6.1 Create `app/skills/` directory and `app/skills/schema.py` with Skill models
    - Define `QualityGate` and `SkillDefinition` Pydantic models
    - Define `QualityGateResult` model for gate evaluation results
    - Create `app/skills/__init__.py`
    - _Requirements: 7.2_

  - [ ] 6.2 Create core Skill YAML definitions in `app/skills/`
    - Create 6 YAML files: `risk_assessment.yaml`, `rain_water_analysis.yaml`, `emergency_plan.yaml`, `resource_dispatch.yaml`, `notification_release.yaml`, `execution_monitoring.yaml`
    - Each defines: id, name, version, trigger_intents, required_inputs, required_tools, agent_sequence, output_schema, quality_gates, fallback_strategy
    - _Requirements: 7.5_

  - [ ]* 6.3 Write property test for Skill schema validation
    - **Property 9: Skill schema validation**
    - **Validates: Requirements 7.2**
    - File: `tests/pbt/test_skill_registry.py`

  - [ ] 6.4 Create `app/platform/skill_registry.py` — SkillRegistry service
    - Implement `SkillRegistry` class with `load_all()`, `lookup_by_intent()`, `get_skill()` methods
    - Load and validate YAML files from `app/skills/` directory
    - Build intent → skill index for fast lookup
    - Log and exclude invalid skills on parse error
    - _Requirements: 7.1, 7.3, 7.4_

  - [ ]* 6.5 Write property test for Skill lookup correctness
    - **Property 8: Skill lookup correctness**
    - **Validates: Requirements 7.4**
    - File: `tests/pbt/test_skill_registry.py` (append)

  - [ ] 6.6 Create `app/platform/skill_executor.py` — SkillExecutor service
    - Implement `SkillExecutor` class with `execute()` and `evaluate_quality_gates()` methods
    - Orchestrate agent execution according to skill's `agent_sequence`
    - Enforce `required_tools` constraint during execution
    - Evaluate all quality gates after completion; trigger fallback_strategy on failure
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 6.7 Write property tests for Skill execution constraints
    - **Property 10: Skill tool constraint enforcement**
    - **Property 11: Quality gate evaluation completeness**
    - **Validates: Requirements 8.3, 8.4, 8.5**
    - File: `tests/pbt/test_skill_executor.py`

  - [ ] 6.8 Integrate SkillRegistry into Supervisor routing
    - In `supervisor_node`, when `skill_registry_enabled` is True, query SkillRegistry for matching skill
    - When skill found, set `active_skill_id` and `skill_agent_sequence` in state
    - When no skill matches, fall back to existing routing logic
    - _Requirements: 8.1, 8.2, 8.6_

- [ ] 7. Checkpoint — Phase 3 complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Phase 4: Resource Dispatch Hardening
  - [ ] 8.1 Create `app/platform/dispatch_validator.py` — Dispatch validation
    - Define `ValidationFailure` and `DispatchValidationResult` models
    - Implement `validate_dispatch_plan()` that checks: resource existence, quantity ≤ available, status == "available", target_location recognized
    - Support partial success: valid allocations proceed, invalid ones rejected with reasons
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ]* 8.2 Write property tests for dispatch validation
    - **Property 12: Dispatch validation invariant**
    - **Property 13: Partial dispatch rejection with continuation**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6**
    - File: `tests/pbt/test_dispatch_validator.py`

  - [ ] 8.3 Create `app/platform/dispatch_state_machine.py` — State machine
    - Define `DispatchState` enum and `VALID_TRANSITIONS` mapping
    - Define `TransitionRecord` model
    - Implement `DispatchStateMachine` class with `can_transition()`, `transition()` methods
    - Raise `InvalidTransitionError` on illegal transitions
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 8.4 Write property tests for dispatch state machine
    - **Property 14: Dispatch state machine transition validity**
    - **Property 15: Dispatch initial state invariant**
    - **Property 16: State transition history recording**
    - **Validates: Requirements 10.2, 10.3, 10.4, 10.5**
    - File: `tests/pbt/test_dispatch_state_machine.py`

  - [ ] 8.5 Create `app/platform/human_in_the_loop.py` — Human approval gateway
    - Define `PendingApproval`, `ApprovalDecision` models and `HIGH_RISK_ACTION_TYPES` set
    - Implement `HumanInTheLoopGateway` class with `submit_for_approval()`, `approve()`, `reject()`, `check_timeout()` methods
    - On timeout, escalate to higher authority level
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

  - [ ]* 8.6 Write property tests for human-in-the-loop
    - **Property 17: High-risk action blocking without approval**
    - **Property 18: Approval audit trail completeness**
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5**
    - File: `tests/pbt/test_human_in_the_loop.py`

  - [ ] 8.7 Integrate dispatch hardening into resource_dispatcher agent
    - In `app/agents/resource_dispatcher.py`, when `dispatch_state_machine_enabled` is True:
      - Validate allocations via `dispatch_validator` before persisting
      - Create dispatch orders with initial state AI_DRAFT
      - Route high-risk actions through `HumanInTheLoopGateway`
    - Preserve existing behavior when flag disabled
    - _Requirements: 9.6, 10.3, 11.1, 11.2_

- [ ] 9. Checkpoint — Phase 4 complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Phase 5: Audit & Observability Layer
  - [ ] 10.1 Create audit record models in `app/platform/audit_models.py`
    - Define `AgentRunRecord`, `ToolCallRecord`, `EvidenceTraceRecord`, `DecisionLogRecord`, `SkillRunRecord` Pydantic models
    - Match fields to the 5 audit database tables defined in design
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [ ] 10.2 Create `app/platform/audit_recorder.py` — AuditRecorder service
    - Implement `AuditRecorder` class with methods: `record_agent_run()`, `record_tool_call()`, `record_evidence_trace()`, `record_decision()`, `record_skill_run()`
    - Write records via Spring Boot API (PlatformClient)
    - Gate behind `audit_tables_enabled` flag; when disabled, no-op
    - Handle API unreachable: buffer in memory (max 100), retry with exponential backoff
    - Handle missing audit tables: log warning, disable gracefully
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 15.4_

  - [ ]* 10.3 Write property tests for audit recording
    - **Property 5: Tool call tracing completeness**
    - **Property 19: Audit record referential integrity**
    - **Validates: Requirements 3.4, 13.1, 13.2, 13.3**
    - File: `tests/pbt/test_audit.py`

  - [ ] 10.4 Create SQL migration for audit tables
    - Create migration file with DDL for: `ai_agent_run`, `ai_tool_call`, `ai_evidence_trace`, `ai_decision_log`, `ai_skill_run`
    - Include indexes on session_id, agent_run_id for query performance
    - Include metadata extension columns for `kb_document` and `kb_chunk`
    - Include `dispatch_order` state column and `dispatch_state_history` table
    - File: `docs/sql/V6__platform_kernel_audit_tables.sql`
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 5.1, 10.5_

  - [ ] 10.5 Instrument agent nodes with audit recording
    - Create a decorator or wrapper that records agent_run start/complete/fail
    - Record tool calls with latency tracking
    - Record evidence trace when citations are used
    - Record routing decisions in decision_log
    - Wire into existing agent nodes in `app/agents/`
    - _Requirements: 3.3, 3.4, 12.1, 12.2, 12.3, 13.1, 13.2_

  - [ ]* 10.6 Write unit tests for audit graceful degradation
    - Test audit recording when API unreachable (buffering behavior)
    - Test audit disabled when tables don't exist
    - Test feature flag disabled → no audit calls
    - File: `tests/unit/test_audit_graceful.py`
    - _Requirements: 15.4_

- [ ] 11. Checkpoint — Phase 5 complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Integration and Wiring
  - [ ] 12.1 Wire all platform components into application startup in `app/main.py`
    - Initialize SkillRegistry (load skills) on startup when flag enabled
    - Initialize AuditRecorder with PlatformClient
    - Initialize HumanInTheLoopGateway
    - Register output validator schema registry
    - Ensure graceful startup when any component fails (log warning, continue)
    - _Requirements: 7.1, 15.3, 15.4_

  - [ ] 12.2 Update `app/graph.py` to conditionally include new nodes
    - Add plan_reviewer, safety_checker nodes when flags enabled
    - Add skill-driven routing edges when skill_registry_enabled
    - Preserve all existing edges and routing unchanged
    - _Requirements: 8.6, 14.1, 14.2, 14.3_

  - [ ]* 12.3 Write integration tests for full workflow with skills
    - Test end-to-end skill execution (intent → skill lookup → agent sequence → quality gates)
    - Test backward compatibility: existing endpoints return same format
    - Test SSE streaming preserved
    - Files: `tests/integration/test_skill_workflow.py`, `tests/integration/test_sse_compat.py`
    - _Requirements: 8.1, 8.2, 14.1, 14.2_

  - [ ]* 12.4 Write integration test for dispatch lifecycle
    - Test full flow: AI draft → validation → approval → dispatch → arrived
    - Test invalid transitions rejected
    - Test human approval blocking
    - File: `tests/integration/test_dispatch_lifecycle.py`
    - _Requirements: 10.1, 10.2, 11.1_

  - [ ]* 12.5 Write integration test for audit trace chain
    - Test decision → evidence → agent_run → tool_call linkage
    - Verify referential integrity across audit tables
    - File: `tests/integration/test_audit_trace_chain.py`
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

- [ ] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each phase
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All new code lives in `water-info-ai/` — no changes to Spring Boot or frontend
- Feature flags allow each phase to be deployed independently with zero risk
- The `app/platform/` package isolates all new platform kernel code from existing agent logic

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3"] },
    { "id": 2, "tasks": ["1.4", "1.5", "2.1", "2.2"] },
    { "id": 3, "tasks": ["2.3", "2.4"] },
    { "id": 4, "tasks": ["2.5", "2.6"] },
    { "id": 5, "tasks": ["2.7"] },
    { "id": 6, "tasks": ["4.1"] },
    { "id": 7, "tasks": ["4.2", "4.4", "4.5"] },
    { "id": 8, "tasks": ["4.3", "4.6", "4.7"] },
    { "id": 9, "tasks": ["6.1"] },
    { "id": 10, "tasks": ["6.2", "6.4"] },
    { "id": 11, "tasks": ["6.3", "6.5", "6.6"] },
    { "id": 12, "tasks": ["6.7", "6.8"] },
    { "id": 13, "tasks": ["8.1", "8.3", "8.5"] },
    { "id": 14, "tasks": ["8.2", "8.4", "8.6", "8.7"] },
    { "id": 15, "tasks": ["10.1"] },
    { "id": 16, "tasks": ["10.2", "10.4"] },
    { "id": 17, "tasks": ["10.3", "10.5", "10.6"] },
    { "id": 18, "tasks": ["12.1", "12.2"] },
    { "id": 19, "tasks": ["12.3", "12.4", "12.5"] }
  ]
}
```
