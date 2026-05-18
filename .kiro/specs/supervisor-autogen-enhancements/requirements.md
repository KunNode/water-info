# Requirements Document

## Introduction

本特性在现有 `water-info-ai` 服务（FastAPI + LangGraph + `audited_agent` 审计层）基础上，借鉴 AutoGen v0.4 的若干设计思想，对 supervisor 多智能体编排做 5 项**增量**增强。目标场景是防汛应急指挥：在 I/II 级响应等高风险节点上，需要可观测、可干预、可恢复、可动态裁剪的工作流。

本特性不替换现有 LangGraph 拓扑、不重写 `FloodGraphState`、不破坏 SSE `trace_update` 事件契约和 `conversation_messages.metadata.reasoning_steps` 数据契约。所有新能力以**特性开关**方式接入，关闭时系统行为与当前一致。

涵盖的 5 个增强：
1. 事件驱动的可观测性（OpenTelemetry tracing 接入）
2. 运行时人工干预机制（Human-in-the-loop pause/resume）
3. Agent 输入/输出契约（消息边界 + Pydantic 校验）
4. 动态拓扑适应（运行时按风险等级裁剪/扩展节点）
5. 任务持久化与中断恢复（中间状态级别的 resume）

## Glossary

- **AI_Service**: 部署在 `water-info-ai/` 的 FastAPI + LangGraph 应用，是本特性所有变更的载体。
- **Supervisor_Node**: `app/agents/supervisor.py` 中的 `supervisor_node` 函数，负责路由决策。
- **Audited_Agent**: `app/platform/agent_audit.py` 中的 `audited_agent` 装饰器，包装每个 LangGraph 节点并写入 `agent_runs / tool_calls / decision_log / evidence_traces` 表。
- **Execution_Trace**: `FloodGraphState.execution_traces` 列表中的单条记录，由 `app/tools/trace.py:make_trace` 构造，对外暴露为 SSE `trace_update` 事件。
- **OTel_Exporter**: 实现 OpenTelemetry SDK 协议的 span 导出器，目标后端 Jaeger/OTLP-compatible collector。
- **Span**: OpenTelemetry 中的一个执行单元，带 trace_id、span_id、attributes、events、status。
- **HITL_Channel**: 人工干预通道，承载暂停事件外发与人工决定回流。MVP 经由 SSE（与现有 `/api/v1/flood/query/stream` 同一通道）外发，回流走 REST `POST /api/v1/flood/approvals/{approval_id}`。
- **Approval_Token**: 暂停时由 AI_Service 产生的字符串 ID，写入 `pending_approvals`，是恢复执行的凭证。
- **Agent_Contract**: 单个 agent 的输入/输出 Pydantic 模型对，声明它从 `FloodGraphState` 读取哪些字段、写回哪些字段。
- **Topology_Profile**: 一组 `(risk_level, intent) → 节点序列覆盖`的规则，决定运行时启用/跳过哪些 agent。
- **Resume_Token**: 用于从已持久化的中间检查点恢复任务的标识符，由 `(session_id, thread_id, checkpoint_id)` 三元组组成。
- **SafetyLevel**: 已存在于 `app/schemas/routing.py`，取值 `NORMAL | ELEVATED | HIGH | CRITICAL`。

## Requirements

### Requirement 1: OpenTelemetry 可观测性接入

**User Story:** 作为 AI_Service 运维人员，我需要把每次路由决策、LLM 调用、工具执行、Agent 节点执行都自动产出为 OpenTelemetry span，以便在 Jaeger/Grafana 中可视化端到端调用链并定位性能与失败问题。

#### Acceptance Criteria

1. WHERE `OTEL_ENABLED=true`, WHEN the AI_Service starts, THE AI_Service SHALL initialize an OpenTelemetry tracer provider with an OTLP/gRPC span exporter targeting the endpoint configured by environment variable `OTEL_EXPORTER_OTLP_ENDPOINT` (defaulting to `http://localhost:4317` when unset), and SHALL complete tracer initialization within 5 seconds.
2. WHERE `OTEL_ENABLED=false` (默认值), THE AI_Service SHALL skip tracer provider initialization and SHALL return a no-op tracer (recording zero spans and issuing zero network calls) for any tracer lookup made by the application.
3. WHERE `OTEL_ENABLED=true`, WHEN an Audited_Agent node starts, THE Audited_Agent SHALL open one Span named `agent.<agent_name>` with attributes `session_id` (string, maximum 128 characters), `agent_run_id` (string, maximum 128 characters), and `iteration` (integer, range 1 to 100).
4. WHERE `OTEL_ENABLED=true`, WHEN an Audited_Agent node completes successfully, THE Audited_Agent SHALL close the Span with status `OK` and attribute `duration_ms` (integer milliseconds, range 0 to 600000).
5. WHERE `OTEL_ENABLED=true`, IF an Audited_Agent node raises an exception, THEN THE Audited_Agent SHALL record the exception on the Span (with `error_message` attribute truncated to a maximum of 1024 characters) and close the Span with status `ERROR` before re-raising.
6. WHERE `OTEL_ENABLED=true`, WHEN Supervisor_Node emits a routing decision, THE Supervisor_Node SHALL attach a Span event named `routing_decision` carrying `next_agent`, `intent`, `safety_level`, and `reasoning` (truncated to a maximum of 2048 characters).
7. WHERE `OTEL_ENABLED=true`, WHEN an LLM call is issued by `app/services/llm.py`, THE AI_Service SHALL record a child Span named `llm.invoke` with attributes `model` (string, maximum 128 characters), `temperature` (float, range 0.0 to 2.0), `prompt_tokens` (integer, range 0 to 200000) and `completion_tokens` (integer, range 0 to 200000) when reported by the provider, and `duration_ms` (integer milliseconds, range 0 to 300000).
8. WHERE `OTEL_ENABLED=true`, WHEN a tool call is recorded as an Execution_Trace with `phase=tool_call`, THE Audited_Agent SHALL emit a child Span named `tool.<tool_name>` with attributes `success` (boolean), `latency_ms` (integer milliseconds, range 0 to 600000), and `error_message` (string truncated to a maximum of 1024 characters, present only when the call failed).
9. THE Audited_Agent SHALL continue writing to `execution_traces`, `agent_runs`, `tool_calls`, `decision_log`, and `evidence_traces` in the existing format, regardless of whether `OTEL_ENABLED` is true or false.
10. WHERE `OTEL_ENABLED=false`, THE AI_Service SHALL produce SSE `trace_update` event payloads (serialized JSON bytes including field order and whitespace) and `conversation_messages.metadata.reasoning_steps` JSONB structure that are byte-for-byte identical to the corresponding outputs produced by the AI_Service version immediately preceding the OpenTelemetry instrumentation change, when given the same input fixture.
11. WHERE `OTEL_ENABLED=true` AND a request reaches `/api/v1/flood/query` or `/api/v1/flood/query/stream`, WHEN the AI_Service returns the HTTP response AND an active root span exists for that request, THE AI_Service SHALL include the response header `X-Trace-Id` whose value is exactly 32 lowercase hexadecimal characters representing the active trace_id.
12. WHERE `OTEL_ENABLED=true`, IF no active root span exists when the AI_Service returns a response for `/api/v1/flood/query` or `/api/v1/flood/query/stream`, THEN THE AI_Service SHALL omit the `X-Trace-Id` response header.
13. WHERE `OTEL_ENABLED=true`, IF tracer provider initialization raises an exception or does not complete within 5 seconds, THEN THE AI_Service SHALL fall back to a no-op tracer, SHALL emit a single warning-level log entry indicating tracer initialization failed, and SHALL continue application startup without raising the failure to the caller.
14. WHERE `OTEL_ENABLED=true`, IF the OTLP collector is unreachable or returns an export error, THEN THE Audited_Agent SHALL drop the affected spans, SHALL NOT block the underlying node for more than 100 milliseconds waiting on export, and SHALL NOT propagate the export error to the request caller.

**Correctness properties:**
- *Invariant*: For any single graph run with N audited node executions, the count of root-level `agent.*` spans emitted equals N (when OTel enabled).
- *Invariant*: Every `tool.*` span has exactly one parent `agent.*` span.
- *Metamorphic*: Toggling `OTEL_ENABLED` between true and false on the same input SHALL produce identical `execution_traces` arrays and identical `decision_log.decision_json` payloads.
- *Error*: When the OTLP collector is unreachable, the Audited_Agent SHALL still complete the underlying node and SHALL NOT raise to the caller (best-effort export).

---

### Requirement 2: 运行时人工干预（Human-in-the-loop）

**User Story:** 作为防汛指挥官，当 Supervisor_Node 即将路由到 SafetyLevel=CRITICAL 的下游节点（如 I 级响应预案生成、跨部门资源调度、对外通知）时，我需要图执行**真正暂停**并把决策推送到指挥端，由我确认、否决或修改后再恢复，而不是仅在状态字段上标记 `human_confirmation_required=true` 然后继续执行。

#### Acceptance Criteria

1. WHERE `HITL_ENABLED=true`, IF a Supervisor_Node decision has `safety_level == CRITICAL`, THEN THE Supervisor_Node SHALL set `next_agent = "__interrupt__"`, allocate a new Approval_Token whose `approval_id` is a UUID v4 string matching `[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}`, and append a row to `pending_approvals` with fields `{approval_id, action_type, action_payload, status: "pending", created_at}` where `created_at` is an ISO-8601 UTC timestamp with millisecond precision (e.g. `2026-05-17T03:14:15.926Z`).
2. WHEN the graph reaches an `__interrupt__` route, THE AI_Service SHALL persist the current LangGraph checkpoint via the existing AsyncPostgresSaver and SHALL stop further graph execution for the current request.
3. WHEN the graph is interrupted on the SSE path, THE AI_Service SHALL emit one SSE event of type `approval_required` carrying `approval_id`, `proposed_next_agent`, `safety_level`, `reasoning`, `action_payload`, and SHALL close the stream when either the event flush to the client completes OR a client disconnect is observed, whichever occurs first; the `pending_approvals` row SHALL remain persisted in both cases so the approval can still be resolved out-of-band.
4. WHEN the graph is interrupted on the non-streaming `/api/v1/flood/query` path, THE AI_Service SHALL return HTTP 202 Accepted with body `{status: "approval_required", approval_id, proposed_next_agent, reasoning}`.
5. WHEN a client calls `POST /api/v1/flood/approvals/{approval_id}` with body `{decision: "approve", override_next_agent?, comment?}`, THE AI_Service SHALL execute an atomic compare-and-set on `pending_approvals.status` from `pending` to `approved` for the given `approval_id`; the AI_Service SHALL resume the graph from the persisted checkpoint with `human_confirmation_required = false` only if the compare-and-set affected exactly one row, and SHALL otherwise route to the failure path defined in AC 8.
6. WHEN the same endpoint is called with `decision == "reject"`, THE AI_Service SHALL execute an atomic compare-and-set on `pending_approvals.status` from `pending` to `rejected` for the given `approval_id`; on success the AI_Service SHALL resume the graph with `next_agent = "__end__"`, append `human_review.rejected_reason` to state (sourced from the request body `comment` field, defaulting to an empty string when `comment` is missing or empty), and skip the proposed action.
7. WHEN the same endpoint is called with `decision == "modify"` AND `override_next_agent` is one of the values matched by the existing `SupervisorDecision.next_agent` regex, THE AI_Service SHALL execute an atomic compare-and-set on `pending_approvals.status` from `pending` to `modified` for the given `approval_id`; on success the AI_Service SHALL resume the graph routing to that agent and SHALL record `human_review.override_reason` in state (sourced from the request body `comment` field, defaulting to an empty string when `comment` is missing or empty).
8. IF the approval_id does not exist OR the compare-and-set in AC 5/6/7 affects zero rows because `status` is no longer `pending`, THEN THE AI_Service SHALL return HTTP 404 (with body `{error_code: "approval_not_found", message: "<human-readable>"}`) or HTTP 409 (with body `{error_code: "approval_already_resolved", message: "<human-readable>", current_status: "<approved|rejected|modified>"}`) respectively, and SHALL NOT mutate any persisted state.
9. THE AI_Service SHALL record the human decision as a `decision_log` row with `decision_type = "human_review"` and `human_approved` equal to `true` for `decision == "approve"`, `false` for `decision == "reject"`, and `true` for `decision == "modify"`.
10. WHERE `HITL_ENABLED=false` (默认值), THE Supervisor_Node SHALL preserve the current behavior: set `human_confirmation_required=true` flag without interrupting execution.
11. THE pending_approvals queue SHALL persist across AI_Service restarts via PostgreSQL so an approval issued before a crash can still be resolved after the service comes back.

**Correctness properties:**
- *Invariant*: A graph run that produces an approval event SHALL NOT have any `agent_runs` rows for the proposed_next_agent until the approval is resolved with `approve` or `modify`.
- *Round-trip*: For any approve→resume cycle, the final state after resume SHALL be equivalent to running the graph end-to-end with `safety_level` artificially lowered (modulo the human_review trace records).
- *Idempotence*: Calling `POST /approvals/{approval_id}` twice with the same payload SHALL succeed once and return HTTP 409 on the second call (no double-resume).
- *Metamorphic*: For any input that does not trigger CRITICAL safety level, the behavior with `HITL_ENABLED=true` SHALL match the behavior with `HITL_ENABLED=false`.

---

### Requirement 3: Agent 输入/输出契约（消息边界）

**User Story:** 作为维护多智能体代码的工程师，我需要每个 agent 显式声明它从 `FloodGraphState` 读取的字段、写回的字段，并在运行前后做 Pydantic 类型校验，以避免 30+ 字段的 TypedDict 在 agent 之间无约束传递、字段名漂移和类型错位。

#### Acceptance Criteria

1. THE AI_Service SHALL define an `AgentContract` interface in `app/agents/_contract.py` exposing `input_model: type[BaseModel]`, `output_model: type[BaseModel]`, and `agent_name: str`.
2. THE AI_Service SHALL provide one concrete `AgentContract` implementation for each of the agents: `data_analyst`, `risk_assessor`, `plan_generator`, `resource_dispatcher`, `notification`, `execution_monitor`, `knowledge_retriever`, `plan_reviewer`, `safety_checker`.
3. WHERE `AGENT_CONTRACTS_ENABLED=true`, WHEN an Audited_Agent runs an agent that has a registered AgentContract, THE Audited_Agent SHALL instantiate `input_model` from the slice of `FloodGraphState` matching `input_model.model_fields` BEFORE invoking the agent body, and SHALL treat any `pydantic.ValidationError` raised by that instantiation as input validation failure.
4. WHERE `AGENT_CONTRACTS_ENABLED=true`, WHEN that same Audited_Agent's wrapped function returns its update dict without raising an exception, THE Audited_Agent SHALL instantiate `output_model` from that update dict BEFORE merging into state, and SHALL treat any `pydantic.ValidationError` raised by that instantiation as output validation failure.
5. IF input validation fails per AC 3, THEN THE Audited_Agent SHALL skip the agent invocation, record an `agent_run` row with `status="failed"` and `error_message` matching the prefix `contract_input_invalid: ` followed by a comma-separated list of every field that Pydantic ValidationError reported as invalid (each entry as `<field_name>=<error_type>`), and SHALL route the graph to `__end__`.
6. IF output validation fails per AC 4, THEN THE Audited_Agent SHALL record an `agent_run` row with `status="failed"` and `error_message` matching the prefix `contract_output_invalid: ` followed by a comma-separated list of every field that Pydantic ValidationError reported as invalid (each entry as `<field_name>=<error_type>`), SHALL NOT merge the malformed update into state, and SHALL route the graph to `__end__`.
7. THE `AgentContract.input_model.model_fields.keys()` SHALL be a superset of `set(_required_context_for_agent(agent_name))` for the same `agent_name`.
8. WHERE `AGENT_CONTRACTS_ENABLED=false` (默认值), THE Audited_Agent SHALL skip Pydantic model instantiation entirely, SHALL NOT emit any `agent_run` row whose `error_message` begins with `contract_input_invalid:` or `contract_output_invalid:`, and SHALL produce `agent_runs`, `decision_log`, and `execution_traces` rows that are byte-for-byte identical to the rows produced by the version of `audited_agent` that existed before this requirement was implemented, when given the same input.
9. THE FloodGraphState TypedDict SHALL retain the same set of keys, the same Python type annotations per key, and the same `Annotated[..., operator.add]` reducer annotations as it has at the time this requirement is accepted.
10. THE AgentContract output_model fields SHALL form a subset of `FloodGraphState` keys so that merging the validated dict into state never introduces unknown keys.
11. WHERE `AGENT_CONTRACTS_ENABLED=true`, WHEN an Audited_Agent runs an agent that does NOT have a registered AgentContract, THE Audited_Agent SHALL skip contract validation for that agent and proceed identically to the `AGENT_CONTRACTS_ENABLED=false` path described in AC 8.

**Correctness properties:**
- *Invariant*: For every agent in scope, `AgentContract.output_model.model_fields.keys()` ⊆ `set(FloodGraphState.__annotations__.keys())`.
- *Invariant*: For every agent in scope, `AgentContract.input_model.model_fields.keys()` ⊇ `set(_required_context_for_agent(agent_name))` (the contract is at least as strict as the supervisor's preflight check).
- *Round-trip*: For any state that passes input validation, the agent output that passes output validation SHALL be parseable by `FloodGraphState` consumers without ad-hoc field defaulting (no `state.get(key) or default` fallbacks needed for declared fields).
- *Metamorphic*: For valid inputs, toggling `AGENT_CONTRACTS_ENABLED` SHALL produce identical agent outputs.

---

### Requirement 4: 动态拓扑适应

**User Story:** 作为防汛业务负责人，我需要工作流在 I 级响应（CRITICAL）时自动加上 `safety_checker` 和 `plan_reviewer` 这两道额外审查、在闲聊或纯数据查询时跳过 `risk_assessor → plan_generator → resource_dispatcher → notification` 这条重链路，而不是把所有路径都硬编码在 `build_flood_response_graph()` 的静态边里。

#### Acceptance Criteria

1. THE AI_Service SHALL define a `TopologyProfile` Pydantic model in `app/agents/_topology.py` with fields `profile_name` (string matching `[a-z][a-z0-9_]{0,63}`), `match` (object with optional keys `risk_level`, `intent`, `safety_level`), `required_agents` (list of strings, length 0 to 16), `skipped_agents` (list of strings, length 0 to 16), and `priority` (integer in range 0 to 1000).
2. THE AI_Service SHALL ship four built-in profiles: `default` (priority 0, empty `match`), `general_chat_fast_path`, `data_only_fast_path`, `critical_response_with_review`.
3. WHERE `DYNAMIC_TOPOLOGY_ENABLED=true`, WHEN Supervisor_Node finishes inferring `intent` and (when available) `risk_level` and `safety_level`, THE Supervisor_Node SHALL select the TopologyProfile with the highest `priority` whose `match` criteria all equal the inferred values via case-sensitive string equality; a `match` key that is omitted is treated as a wildcard for that key only, and a `match` key that is present SHALL match exactly.
4. IF two or more TopologyProfiles match an input with equal highest priority, THEN THE Supervisor_Node SHALL deterministically select the one whose `profile_name` sorts first lexicographically (Unicode codepoint order).
5. IF no TopologyProfile's `match` criteria are satisfied, THEN THE Supervisor_Node SHALL fall back to the `default` profile.
6. WHEN a TopologyProfile lists an agent in `skipped_agents`, THE Supervisor_Node SHALL never route to that agent for the rest of the current graph run, even if the deterministic router or LLM proposes it; the skipped agent name SHALL be recorded under `state.routing_decision.overrides.skipped`.
7. WHEN a TopologyProfile lists an agent in `required_agents`, THE Supervisor_Node SHALL ensure that agent has produced an `agent_runs` row before the workflow ends; if multiple required agents have not yet run, THE Supervisor_Node SHALL route to them in the order they appear in `required_agents`, before routing to `__end__`.
8. WHERE the matching profile is `critical_response_with_review`, THE Supervisor_Node SHALL route through `safety_checker` first and then `plan_reviewer` after `plan_generator` completes and before `resource_dispatcher` runs.
9. WHERE the matching profile is `general_chat_fast_path` (intent=`general_chat` AND risk_level in {`none`, `low`}), THE Supervisor_Node SHALL route directly `conversation_assistant → final_response` without invoking `data_analyst`, `risk_assessor`, `plan_generator`, `resource_dispatcher`, or `notification`.
10. WHERE the matching profile is `data_only_fast_path` (`answer_policy.data_only=true`), THE Supervisor_Node SHALL route through `data_analyst → final_response` and SHALL skip `risk_assessor`, `plan_generator`, `resource_dispatcher`, `notification`, `safety_checker`, and `plan_reviewer`.
11. THE static graph compiled by `build_flood_response_graph()` SHALL include all node definitions; dynamic adaptation happens through Supervisor_Node decisions and `conditional_edges`, NOT through recompiling the StateGraph at runtime.
12. WHERE `DYNAMIC_TOPOLOGY_ENABLED=true`, THE selected `profile_name` SHALL be written to `state.routing_decision.topology_profile`, and exactly one Execution_Trace SHALL be emitted per graph run with `phase="data_query"` and `title` equal to `拓扑适应: <profile_name>`.
13. WHERE `DYNAMIC_TOPOLOGY_ENABLED=false` (默认值), THE Supervisor_Node SHALL bypass profile selection entirely, SHALL NOT enforce `skipped_agents` or `required_agents`, SHALL NOT write `state.routing_decision.topology_profile`, and SHALL NOT emit the `拓扑适应: ...` Execution_Trace.
14. IF profile selection raises an exception during runtime, THEN THE Supervisor_Node SHALL fall back to the `default` profile, SHALL emit a single warning-level log entry identifying the failed profile and the exception type, and SHALL continue routing using the default profile without raising the failure to the caller.

**Correctness properties:**
- *Invariant*: For any graph run, the set of agents actually executed SHALL be a subset of (all agents in the static graph) MINUS (skipped_agents of the chosen profile).
- *Invariant*: For any graph run that ends in `__end__`, every agent name in (chosen profile).required_agents SHALL appear at least once in `agent_runs` rows for that session.
- *Confluence*: For two profiles that match the same input with equal priority, profile selection SHALL be deterministic (ties broken by lexicographic profile_name).
- *Metamorphic*: Adding a new profile with `priority` lower than `default` SHALL NOT change behavior for any existing input.

---

### Requirement 5: 任务持久化与中断恢复

**User Story:** 作为长时应急响应任务的发起人，我需要在 `risk_assessor` 完成后服务重启、网络中断或人工干预暂停的情况下，能够使用 `Resume_Token` 从中间节点继续执行，而不必重新跑完 `data_analyst → risk_assessor` 的前置链路。

#### Acceptance Criteria

1. WHERE `LANGGRAPH_POSTGRES_ENABLED=true`, WHEN an Audited_Agent node completes, THE AI_Service SHALL persist a checkpoint via the existing AsyncPostgresSaver (scoped by `thread_id = session_id`) before the next agent node begins execution.
2. THE AI_Service SHALL expose `GET /api/v1/flood/sessions/{session_id}/checkpoints` returning a JSON list of up to 50 most recent checkpoint records ordered by `created_at` descending, each record containing `{checkpoint_id, last_completed_agent, created_at, current_state_summary}`.
3. THE AI_Service SHALL expose `POST /api/v1/flood/sessions/{session_id}/resume` with body `{checkpoint_id?, override_next_agent?}`; on successful resume the AI_Service SHALL return HTTP 200 with body `{status: "resumed", run_id, checkpoint_id}` where `run_id` identifies the resumed graph run.
4. WHEN resume is invoked WITHOUT `checkpoint_id` AND at least one checkpoint exists for the session, THE AI_Service SHALL use the checkpoint with the highest `created_at` for that session.
5. WHEN resume is invoked WITH `override_next_agent` AND that value matches the existing `SupervisorDecision.next_agent` regex, THE AI_Service SHALL update state with that next_agent before continuing the graph; `override_next_agent` is NOT required to equal `last_completed_agent` or any successor of it.
6. IF the requested `checkpoint_id` does not exist for the given session, THEN THE AI_Service SHALL return HTTP 404 and SHALL NOT modify state.
7. IF `LANGGRAPH_POSTGRES_ENABLED=false`, THEN THE resume endpoints (`GET /sessions/{session_id}/checkpoints` and `POST /sessions/{session_id}/resume`) SHALL return HTTP 503 with a JSON error payload indicating that persistence is disabled.
8. WHEN execution is resumed, THE Audited_Agent SHALL emit exactly one Execution_Trace with `phase="data_query"` whose `title` includes the value of `last_completed_agent` so the SSE consumer can identify the resumption point.
9. THE checkpoint payload SHALL include all FloodGraphState fields currently in use, specifically `routing_decision`, `skill_quality_results`, `evidence_context`, `risk_assessment`, `emergency_plan`, `resource_plan`, `notifications`, `execution_progress`.
10. WHEN the resumed run reaches `__end__`, THE AI_Service SHALL produce a final response that incorporates the work already persisted in the checkpoint, and SHALL NOT re-execute any agent whose `agent_runs` row exists in the checkpoint with `status="completed"`.
11. WHEN `POST /resume` is called twice with identical body and the same `checkpoint_id` AND the first call's resumed run is still in progress or has completed without a new checkpoint being created, THE AI_Service SHALL return HTTP 409 on the second call and SHALL NOT create duplicate `agent_runs` rows for nodes already completed in the original checkpoint.
12. IF persisting a checkpoint fails (e.g. the AsyncPostgresSaver raises an exception), THEN THE AI_Service SHALL emit a single warning-level Execution_Trace identifying the failed agent, SHALL continue the current graph run without raising the failure to the caller, and SHALL NOT create a partial or corrupted checkpoint row.
13. IF `POST /resume` is invoked for a session that has zero checkpoints, THEN THE AI_Service SHALL return HTTP 404 with an error payload indicating no checkpoints exist for the session, and SHALL NOT modify any persisted state.

**Correctness properties:**
- *Round-trip*: For any graph run that reaches `__end__` without interruption, persisting after each node and resuming from the last checkpoint SHALL produce a final state equivalent to a fresh run on the same input.
- *Round-trip*: For an interrupted run resumed from checkpoint K, the union of `agent_runs` for the original partial run and the resumed run SHALL equal the `agent_runs` of an uninterrupted run on the same input (modulo timestamps and the resume trace).
- *Invariant*: Checkpoint records SHALL be append-only within a `thread_id`; resuming SHALL NOT delete or rewrite earlier checkpoints.
- *Idempotence*: `POST /resume` called twice with identical body and the same `checkpoint_id` SHALL produce one extra graph run; the second call SHALL be detected by checkpoint-id+state-hash and rejected with HTTP 409 if the underlying checkpoint has already been consumed in the same way.
- *Error*: Resuming from a checkpoint whose state does not contain the fields required by `override_next_agent`'s AgentContract (Requirement 3) SHALL fail with HTTP 422 and a clear `missing_context` list, NOT silently re-route.
