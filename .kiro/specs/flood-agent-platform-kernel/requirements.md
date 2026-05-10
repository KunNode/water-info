# Requirements Document — 防汛智能体平台内核 (Flood Agent Platform Kernel)

## Introduction

本需求文档定义了将现有 LangGraph 多智能体防汛系统升级为产品化"防汛智能体平台内核"的功能需求。升级覆盖五个层次：多智能体平台层（结构化输出与任务总控）、RAG 知识层（决策前置证据）、技能注册层（防汛 SOP 编排）、资源调度强化层（强约束与人机协同）、审计与可观测层（全链路追踪）。所有变更为增量升级，不破坏现有多智能体工作流和 API 端点。

## Glossary

- **Supervisor**: 多智能体系统的任务总控节点，负责意图识别、路由决策和工作流编排
- **Agent**: LangGraph 工作流中的独立处理节点，执行特定领域任务（如风险评估、预案生成）
- **FloodGraphState**: LangGraph 共享状态 TypedDict，所有 Agent 通过读写此状态交换数据
- **Skill**: 可配置的操作规程模板，定义触发意图、所需输入、工具序列、输出约束和质量门
- **Skill_Registry**: 技能注册中心，负责加载、校验和索引所有 Skill 定义
- **RAG**: 检索增强生成，从知识库检索相关文档片段作为 LLM 推理的证据
- **Evidence**: 从知识库检索到的引用片段，包含 citation_id、内容、来源和评分
- **Dispatch_Order**: 资源调度单，记录物资/人员从来源到目的地的调度指令
- **Dispatch_State_Machine**: 调度单生命周期状态机，管理从草稿到完成的状态流转
- **Human_In_The_Loop**: 人机协同机制，高风险操作需人工审核批准后方可执行
- **Agent_Run**: 单次 Agent 执行的完整记录，包含输入状态、输出状态、耗时和错误信息
- **Decision_Log**: 决策审计日志，记录决策类型、证据引用、人工审批状态
- **Plan_Reviewer**: 预案校验 Agent，对生成的应急预案进行合规性和安全性验证
- **Safety_Checker**: 安全检查 Agent，对高风险操作进行安全约束校验
- **Quality_Gate**: 技能执行的质量检查点，验证输出是否满足预定义标准

## Requirements

### Requirement 1: Supervisor 结构化路由决策

**User Story:** As a 防汛值班人员, I want the Supervisor to produce structured routing decisions with explicit reasoning, so that every routing choice is auditable and downstream agents receive precise context.

#### Acceptance Criteria

1. WHEN a user query is received, THE Supervisor SHALL output a structured routing decision containing fields: intent, next_agent, required_context, missing_context, reasoning, and safety_level
2. THE Supervisor SHALL assign safety_level as one of: normal, elevated, high, critical
3. WHEN safety_level is high or critical, THE Supervisor SHALL include a human_confirmation_required flag set to true in the routing decision
4. THE Supervisor SHALL generate a unique agent_run_id (UUID v4) for each routing decision and attach it to the state
5. WHEN the Supervisor cannot determine intent with confidence, THE Supervisor SHALL set missing_context with specific fields needed and route to data_analyst for grounding
6. THE Supervisor SHALL maintain backward compatibility with the existing deterministic routing logic as a fallback when LLM routing fails

### Requirement 2: Agent 标准化结构化输出

**User Story:** As a 系统运维人员, I want every Agent to produce output conforming to a standardized schema, so that downstream consumers can reliably parse and validate agent results.

#### Acceptance Criteria

1. THE Risk_Assessor SHALL output a structured result containing: risk_level, risk_score, affected_stations, response_level, reasoning, and citations
2. THE Plan_Generator SHALL output a structured result containing: actions, resources, notifications, trigger_conditions, and citations
3. THE Resource_Dispatcher SHALL output a structured result containing: resource_plan (array of allocations), dispatch_id, resource_id, and status for each allocation
4. THE Execution_Monitor SHALL output a structured result containing: progress_pct, blocked_actions, and recommendations
5. WHEN an Agent output fails schema validation, THE Platform SHALL log the validation error, attach the raw output to the agent_run record, and return a graceful degradation response
6. THE Platform SHALL validate each Agent output against its registered Pydantic schema before writing to FloodGraphState

### Requirement 3: Agent 间通信约束

**User Story:** As a 系统架构师, I want Agents to communicate exclusively through shared State and Tool calls, so that the system maintains a clear data flow and avoids hidden coupling.

#### Acceptance Criteria

1. THE Platform SHALL enforce that no Agent directly invokes another Agent's function; all inter-agent data exchange occurs through FloodGraphState fields
2. WHEN an Agent needs data produced by another Agent, THE requesting Agent SHALL read the relevant field from FloodGraphState
3. THE Platform SHALL generate a unique agent_run_id for each Agent execution and record it in the execution trace
4. WHEN an Agent invokes a Tool, THE Platform SHALL record the tool_name, input parameters, output, success status, and latency in the agent_run context

### Requirement 4: RAG 三模式知识检索

**User Story:** As a 防汛决策人员, I want the knowledge retrieval system to support three distinct modes (问答、预案前置、决策校验), so that evidence is injected at the appropriate stage of the decision workflow.

#### Acceptance Criteria

1. WHEN the intent is knowledge_qa, THE Knowledge_Retriever SHALL operate in answer mode: retrieve evidence, synthesize a cited response, and terminate the workflow
2. WHEN the intent requires risk assessment or plan generation and risk_level is moderate or higher, THE Knowledge_Retriever SHALL operate in preflight mode: retrieve evidence and inject it into evidence_context for downstream agents
3. WHEN a plan or dispatch decision has been generated, THE Plan_Reviewer SHALL operate in validation mode: retrieve relevant regulations and verify the generated result against them
4. THE Knowledge_Retriever SHALL support metadata-filtered retrieval using fields: doc_type, region_code, basin_code, station_id, effective_date, expire_date, authority_level, and risk_level_applicable
5. WHEN metadata filters are provided, THE Knowledge_Retriever SHALL apply them as pre-filter conditions before vector similarity search

### Requirement 5: 知识库领域元数据扩展

**User Story:** As a 知识库管理员, I want domain-specific metadata attached to every knowledge document, so that retrieval can be scoped to the correct region, time period, and authority level.

#### Acceptance Criteria

1. THE Platform SHALL store the following metadata fields for each knowledge document chunk: doc_type, region_code, basin_code, station_id, effective_date, expire_date, authority_level, and risk_level_applicable
2. WHEN a document's expire_date has passed, THE Knowledge_Retriever SHALL exclude it from retrieval results unless explicitly requested
3. WHEN region_code or basin_code is available in the query context, THE Knowledge_Retriever SHALL prioritize documents matching the geographic scope
4. THE Platform SHALL validate metadata fields against predefined enumerations (doc_type: regulation, manual, sop, template, case_study; authority_level: national, provincial, municipal, district)

### Requirement 6: Plan_Reviewer 与 Safety_Checker Agent

**User Story:** As a 防汛指挥长, I want generated plans and high-risk actions to be automatically validated against regulations and safety constraints, so that non-compliant decisions are flagged before execution.

#### Acceptance Criteria

1. WHEN Plan_Generator produces an emergency plan, THE Plan_Reviewer SHALL validate the plan against retrieved regulatory evidence and output a compliance_result containing: compliant (boolean), violations (list), suggestions (list), and cited_regulations
2. WHEN a dispatch order or notification involves high-risk actions (evacuation, road closure, service suspension), THE Safety_Checker SHALL verify the action against safety constraints and output: safe_to_proceed (boolean), risk_factors (list), required_approvals (list)
3. IF Plan_Reviewer identifies a violation, THEN THE Platform SHALL flag the plan as requiring revision and return it to Plan_Generator with the violation details
4. IF Safety_Checker determines safe_to_proceed is false, THEN THE Platform SHALL block the action and require human approval before proceeding

### Requirement 7: Skill 注册与定义

**User Story:** As a 平台开发者, I want operational procedures defined as declarative YAML Skills with standardized schemas, so that new workflows can be added without code changes.

#### Acceptance Criteria

1. THE Skill_Registry SHALL load Skill definitions from YAML files located in the app/skills/ directory
2. THE Platform SHALL validate each Skill definition against a JSON Schema requiring fields: id, name, version, trigger_intents (list), required_inputs (list), required_tools (list), agent_sequence (list), output_schema (reference), quality_gates (list), and fallback_strategy
3. WHEN a Skill definition fails schema validation at startup, THE Skill_Registry SHALL log the error and exclude the invalid Skill from the active registry
4. THE Skill_Registry SHALL provide a lookup method that accepts an intent string and returns the matching Skill definition or null
5. THE Platform SHALL include six core Skills at launch: rain_water_situation_analysis, risk_assessment, emergency_plan_generation, resource_dispatch, notification_release, and execution_monitoring

### Requirement 8: Skill 驱动的工作流编排

**User Story:** As a 防汛值班人员, I want the Supervisor to select and execute Skills that determine the agent sequence and tool constraints, so that responses follow standardized operational procedures.

#### Acceptance Criteria

1. WHEN the Supervisor identifies an intent, THE Supervisor SHALL query the Skill_Registry for a matching Skill
2. WHEN a matching Skill is found, THE Supervisor SHALL follow the Skill's agent_sequence to determine the next agent instead of using default routing logic
3. WHILE a Skill is executing, THE Platform SHALL enforce the Skill's required_tools constraint: only tools listed in the Skill definition are available to agents within that execution
4. WHEN a Skill execution completes, THE Platform SHALL evaluate all quality_gates defined in the Skill and record pass/fail results
5. IF a quality_gate fails, THEN THE Platform SHALL execute the Skill's fallback_strategy (retry, degrade, or escalate_to_human)
6. THE Platform SHALL maintain backward compatibility: when no Skill matches the intent, the existing deterministic and LLM-based routing logic applies

### Requirement 9: 资源调度强约束

**User Story:** As a 应急物资管理员, I want resource dispatch to enforce strict validation rules, so that LLM-generated dispatch plans cannot create invalid or unauthorized orders.

#### Acceptance Criteria

1. THE Resource_Dispatcher SHALL validate that every resource_id in a dispatch plan exists in the inventory system before creating a dispatch order
2. THE Resource_Dispatcher SHALL validate that the requested quantity does not exceed the available inventory quantity for each resource
3. THE Resource_Dispatcher SHALL validate that the resource status is "available" before including it in a dispatch order
4. THE Resource_Dispatcher SHALL validate that the target_location is a recognized location identifier
5. WHEN any validation fails, THE Resource_Dispatcher SHALL reject the specific allocation, log the validation failure, and continue processing remaining allocations
6. THE Platform SHALL enforce that LLM-generated resource plans are treated as candidates only; no dispatch order is persisted without passing all validation rules

### Requirement 10: 调度单状态机

**User Story:** As a 调度指挥员, I want dispatch orders to follow a defined lifecycle with clear state transitions, so that the status of every resource movement is trackable.

#### Acceptance Criteria

1. THE Dispatch_State_Machine SHALL define the following states: AI_DRAFT, APPROVED, DISPATCHED, ARRIVED, RETURNED, CANCELLED
2. THE Dispatch_State_Machine SHALL enforce valid transitions: AI_DRAFT → APPROVED, AI_DRAFT → CANCELLED, APPROVED → DISPATCHED, APPROVED → CANCELLED, DISPATCHED → ARRIVED, DISPATCHED → CANCELLED, ARRIVED → RETURNED
3. WHEN a dispatch order is created by the AI system, THE Platform SHALL set its initial state to AI_DRAFT
4. WHEN a state transition is attempted that violates the allowed transitions, THE Platform SHALL reject the transition and return an error indicating the current state and attempted target state
5. THE Platform SHALL record each state transition with timestamp, operator_id, and reason in the dispatch order history

### Requirement 11: 高风险操作人机协同

**User Story:** As a 防汛指挥长, I want high-risk actions to require human approval before execution, so that critical decisions are not made autonomously by the AI system.

#### Acceptance Criteria

1. THE Platform SHALL classify the following actions as requiring human approval: creating formal dispatch orders (AI_DRAFT → APPROVED), sending external notifications, escalating response levels, and issuing evacuation/closure/suspension directives
2. WHEN a high-risk action is generated, THE Platform SHALL present it as a recommendation with supporting evidence and wait for human approval
3. WHEN a human approves an action, THE Platform SHALL record the approver_id, approval_timestamp, and approval_reason in the decision_log
4. WHEN a human rejects an action, THE Platform SHALL record the rejection reason and allow the operator to provide alternative instructions
5. WHILE awaiting human approval, THE Platform SHALL not execute the pending action and SHALL display the pending status to the operator
6. IF no human approval is received within a configurable timeout period, THEN THE Platform SHALL escalate the pending action to a higher authority level

### Requirement 12: Agent 执行审计记录

**User Story:** As a 审计人员, I want every Agent execution to be recorded with full input/output state, so that any decision can be traced back to its inputs and reasoning.

#### Acceptance Criteria

1. THE Platform SHALL record each Agent execution in the ai_agent_run table with fields: id, session_id, agent_run_id, agent_name, input_state_json, output_state_json, status (started, completed, failed), started_at, finished_at, and error_message
2. THE Platform SHALL record each Tool call in the ai_tool_call table with fields: id, agent_run_id, tool_name, input_json, output_json, success (boolean), latency_ms, and error_message
3. THE Platform SHALL record each evidence citation usage in the ai_evidence_trace table with fields: id, session_id, citation_id, document_id, chunk_id, score, used_by_agent, and used_in_field
4. THE Platform SHALL record each decision in the ai_decision_log table with fields: id, session_id, decision_type, decision_json, evidence_ids, human_approved (boolean), approved_by, and approved_at
5. THE Platform SHALL record each Skill execution in the ai_skill_run table with fields: id, skill_id, skill_version, session_id, agent_run_id, input_json, output_json, and quality_check_result

### Requirement 13: 全链路可追溯性

**User Story:** As a 防汛指挥长, I want to trace any decision back to its evidence, tool calls, and approval chain, so that post-incident review can reconstruct the complete decision path.

#### Acceptance Criteria

1. THE Platform SHALL link every ai_decision_log entry to its supporting ai_evidence_trace entries via evidence_ids
2. THE Platform SHALL link every ai_tool_call entry to its parent ai_agent_run entry via agent_run_id
3. THE Platform SHALL link every ai_skill_run entry to its constituent ai_agent_run entries via session_id and agent_run_id
4. WHEN a decision is queried for audit, THE Platform SHALL return the complete trace chain: decision → evidence used → agent runs involved → tool calls made → human approvals
5. THE Platform SHALL retain all audit records for a minimum of 3 years in compliance with emergency management record-keeping requirements

### Requirement 14: 向后兼容性保障

**User Story:** As a 前端开发者, I want the platform kernel upgrade to preserve all existing API endpoints and response formats, so that the frontend application continues to function without modification.

#### Acceptance Criteria

1. THE Platform SHALL maintain all existing API endpoints (/api/v1/flood/query, /api/v1/flood/query/stream, /api/v1/plans, /api/v1/sessions) with unchanged request and response schemas
2. THE Platform SHALL maintain the existing SSE streaming format for /api/v1/flood/query/stream
3. WHEN the Skill_Registry or structured output validation is unavailable, THE Platform SHALL fall back to the existing agent routing and output handling logic
4. THE Platform SHALL not modify the existing FloodGraphState TypedDict fields; new fields are additive only
5. THE Platform SHALL maintain the existing execution_traces format while extending it with additional metadata (agent_run_id, skill_id)

### Requirement 15: 增量部署与配置

**User Story:** As a 运维工程师, I want each platform layer to be independently toggleable via configuration, so that upgrades can be rolled out incrementally without all-or-nothing deployment.

#### Acceptance Criteria

1. THE Platform SHALL provide feature flags for each layer: structured_output_enabled, skill_registry_enabled, dispatch_state_machine_enabled, audit_tables_enabled, plan_reviewer_enabled
2. WHEN a feature flag is disabled, THE Platform SHALL bypass the corresponding layer and use existing behavior
3. THE Platform SHALL load feature flags from environment variables with sensible defaults (all disabled for initial deployment)
4. WHEN audit_tables_enabled is true but the audit tables do not exist in the database, THE Platform SHALL log a warning and disable audit recording gracefully without crashing
