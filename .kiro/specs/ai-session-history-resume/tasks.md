# Implementation Plan: AI Session History Resume

## Overview

打通「点击历史会话 → 还原完整消息（含思维链与工具轨迹）→ 基于全量上下文续聊」的端到端链路。实现分三层：
- **前端还原层**（water-info-admin / Vue 3 + TypeScript + Pinia）：扩展 `loadSession`，把 `conversation_messages.metadata` 中的 `reasoning_steps` / `execution_traces` / `tool_calls` 映射回 `ChatMessageItem`；补齐抽屉自动关闭、失败提示与键盘可达。
- **后端上下文层**（water-info-ai / Python 3.11 + FastAPI + LangGraph）：在 `MemoryService.load_context` 中把读库失败提升为 `MemoryLoadError`；新增 `session_context_payload` 让每个 LLM-invoking Agent 都注入记忆；扩展 `event_stream` 最终元数据写入完整 schema。
- **契约层**：`conversation_messages.metadata` JSONB（`reasoning_steps` / `execution_traces` / `tool_calls` / `agent` / `version`）作为写入端与还原端的单一事实源。

共定义 6 条 Correctness Properties，分别用 `@fast-check/vitest`（前端）与 `hypothesis`（后端）做属性测试，至少 100 次迭代。

## Tasks

- [x] 1. Backend: Memory service 加固（`MemoryLoadError` + 全量历史读取）
  - [x] 1.1 在 `water-info-ai/app/memory/service.py` 中引入 `MemoryLoadError` 异常类与 `CONTEXT_HISTORY_LIMIT` 配置项
    - 新增 `class MemoryLoadError(RuntimeError)`，构造参数为失败来源字符串（如 `"summary"` / `"snapshot"` / `"conversation_messages"`）
    - 从 `app.config.settings` 读取 `memory_context_history_limit`（默认 20），在模块级常量 `CONTEXT_HISTORY_LIMIT` 暴露
    - 若 `settings` 暂无该字段，在 `app/config.py` 的 Pydantic Settings 中补齐 `memory_context_history_limit: int = 20`
    - _Requirements: 3.2, 4.4_

  - [x] 1.2 重构 `MemoryService.load_context`：强制加载 summary / snapshot / recent_messages，并在关键读失败时抛出 `MemoryLoadError`
    - `get_latest_conversation_summary` / `get_conversation_snapshot` / `get_conversation_messages` 三个调用的 `except Exception` 分支改为 `raise MemoryLoadError(source) from exc`
    - `recent_session_messages` 必须总是尝试从 DB 读取至多 `CONTEXT_HISTORY_LIMIT` 条，即使调用方传入了预填历史
    - 非关键路径（`search_memory_items` / embedding 搜索）保留原有降级行为
    - 保证返回的 `recent_messages` 按数据库 `id` 升序；每条 `role ∈ {user, assistant}`、`content` 非空
    - _Requirements: 3.2, 3.3, 4.4_

  - [x] 1.3 为 `MemoryService.load_context` 编写属性测试（Property 3）
    - **Property 3: `MemoryService.load_context` 完整性**
    - **Validates: Requirements 3.2, 3.3**
    - 使用 `hypothesis` 生成 0 ≤ N ≤ `CONTEXT_HISTORY_LIMIT` 条 `role ∈ {user, assistant}`、`status='completed'` 的消息，以及可选的快照与摘要行
    - 用 `pytest-asyncio` + 内存伪造的 `DatabaseService`（mock）驱动 `load_context`
    - 断言：`len(result.recent_messages) == 过滤后 DB 消息数`、顺序按 `id` 升序、`snapshot.session_id == session_id`、`summary` 等于最新行的 `summary` 字段
    - 标签：`Feature: ai-session-history-resume, Property 3: load_context completeness`
    - 至少 100 次迭代
    - _Requirements: 3.2, 3.3_

- [x] 2. Backend: 统一 prompt 记忆注入（`session_context_payload`）
  - [x] 2.1 新建 `water-info-ai/app/agents/_prompt.py` 并导出 `session_context_payload(state: dict) -> dict`
    - 返回顶层键 `conversation_summary` / `recent_session_messages` / `business_snapshot` / `long_term_memories`
    - 所有字段在 `memory_context` 缺失时必须返回安全默认值（空字符串 / 空列表 / 空字典）
    - 使用 `to_plain_data` 深拷贝确保 payload 可 JSON 序列化
    - _Requirements: 3.4_

  - [x] 2.2 在所有 LLM-invoking Agent 中用 `session_context_payload(state)` 取代各自拼装 `memory_context`
    - 改造节点：`agents/supervisor.py`、`agents/conversation_assistant.py`、`agents/risk_assessor.py`、`agents/plan_generator.py`、`agents/final_response.py`
    - 补齐当前缺口节点：`agents/data_analyst.py`、`agents/resource_dispatcher.py`、`agents/notification_agent.py`、`agents/execution_monitor.py`、`agents/knowledge_retriever.py`（若存在）——在构造 prompt 时也必须把 `"memory_context": session_context_payload(state)` 放入顶层
    - 统一 key 名为 `memory_context`
    - _Requirements: 3.4, 3.5_

  - [x] 2.3 为每个 LLM Agent 编写属性测试（Property 4）
    - **Property 4: 每个 LLM Agent 的 prompt 都包含 `memory_context`**
    - **Validates: Requirements 3.4**
    - 使用 `hypothesis` 生成任意非空 `memory_context`（`recent_session_messages / business_snapshot / conversation_summary / long_term_memories` 中至少一项非空）
    - Mock `ChatOpenAI`（或等价 LLM 客户端）的 `ainvoke` 捕获传入 payload，对每个节点（`supervisor`, `conversation_assistant`, `risk_assessor`, `plan_generator`, `final_response`）断言 `payload["memory_context"]` 与 `session_context_payload(state)` 深度相等
    - 标签：`Feature: ai-session-history-resume, Property 4: memory_context ubiquity`
    - 至少 100 次迭代
    - _Requirements: 3.4_

- [x] 3. Backend: 持久化 schema 与 SSE 错误事件
  - [x] 3.1 在 `water-info-ai/app/main.py` 中新增最终元数据构造工具函数
    - 新增 `_reasoning_steps_from_final_state(final_state)` 把 `execution_traces` + 思考步骤合并为前端 `ReasoningStep[]` 形态（字段 `id/kind/title/content/status/started_at/ended_at/duration_ms/tool`）
    - 新增 `_tool_calls_from_traces(traces)` 把 tool 类 trace 摊平为 `tool_calls[]`（字段 `tool_call_id/tool_name/arguments/result/error/duration_ms`）
    - 两个函数为纯函数，便于独立测试
    - _Requirements: 2.2, 2.3, 3.6_

  - [x] 3.2 扩展 `event_stream()` 的最终消息写入，遵循 JSONB 契约
    - 在 streaming 循环结束后构造 `trace_metadata = {"version": 1, "agent": ..., "reasoning_steps": ..., "execution_traces": ..., "tool_calls": ...}`
    - 调用 `db.update_message_content(assistant_msg_id, final_response, status="completed", metadata=trace_metadata)`
    - 确保 `agent` 字段落到 `final_state["current_agent"]`（若缺失回退 `"final_response"`）
    - 时间戳统一毫秒级 UNIX（与前端 `Date.now()` 对齐）
    - _Requirements: 2.2, 2.3, 2.4, 3.6_

  - [x] 3.3 把 `MemoryLoadError` 映射为结构化 SSE `error` 事件并终止流
    - 在 `memory_loader_node` 中捕获 `MemoryLoadError`，在状态里写入 `{"memory_context": {}, "error": "memory_load_failed: <source>", "next_agent": "__end__"}`
    - 在 `event_stream` 中检测该错误状态，`yield _event_line({"type": "error", "message": "会话历史加载失败，请稍后重试", "code": "memory_load_failed", "recoverable": False})` 并 `return`
    - 同时写入 loguru 错误日志（包含 `session_id` 与失败来源）
    - _Requirements: 4.4_

  - [x] 3.4 集成 smoke 测试：验证 AI 在 Loaded_Session 中能引用历史实体
    - **Validates: Requirements 3.5**
    - 使用 `pytest-asyncio` + 真实 LangGraph 调用（可 mock LLM 返回固定文本模板）
    - 预置 DB 种子：一条历史会话包含 `"翠屏湖"` / `"风险等级: high"` 等实体的 user+assistant 消息
    - 对同一 `session_id` 发起 `/api/v1/flood/query/stream` 请求，断言 `final_response` 中包含历史实体（通过 prompt 模板注入可验证）
    - 仅 1-2 个 case，不做属性化 100 次迭代
    - _Requirements: 3.5_

- [x] 4. Checkpoint — 后端阶段
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Frontend: 消息反序列化（`mapServerMessageToChatItem`）
  - [x] 5.1 在 `water-info-admin/src/stores/aiConversation.ts` 中新增映射工具函数
    - 新增私有函数 `mapServerMessageToChatItem(m: ConversationMessage): ChatMessageItem`：还原 `id/role/content/timestamp/status/reasoning/answer/traces`
    - 新增 `deserializeReasoningState(steps, ts): ReasoningState`：hydrate `kind/title/content/status/startedAt/endedAt/durationMs/tool`，history 模式统一 `status='success'`、`expanded=false`、`isDefaultExpand=false`
    - 新增 `deserializeExecutionTrace(raw): Trace`：透传 `phase/status/title/detail/tool_name/metadata`
    - `reasoning` 仅在 `role==='assistant'` 且 `metadata.reasoning_steps` 非空时填充；`traces` 仅在 `metadata.execution_traces` 非空时填充；两者缺失必须返回 `undefined`（不渲染空壳）
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [x] 5.2 为 `mapServerMessageToChatItem` 编写属性测试（Property 2）
    - **Property 2: 消息持久化与还原 round-trip**
    - **Validates: Requirements 2.2, 2.3, 2.4, 2.5, 3.6**
    - 使用 `@fast-check/vitest` 生成任意合法 `metadata`（含空数组、缺字段、混合 `kind=thought|tool`、缺失 `reasoning_steps`/`execution_traces`）
    - 断言：
      - `metadata.reasoning_steps` 非空 → `output.reasoning.steps.length === input.length`，每步 `title/content/kind/status/tool.name` 等价
      - `metadata.execution_traces` 非空 → `output.traces.length === input.length`，`phase/status/title/tool_name` 等价
      - 两者均空或缺失 → `output.reasoning === undefined` 且 `output.traces === undefined`
      - `user` 角色消息始终 `reasoning === undefined`
    - 标签：`Feature: ai-session-history-resume, Property 2: metadata round-trip`
    - 至少 100 次迭代
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 3.6_

- [x] 6. Frontend: `loadSession` 原子性与失败保留
  - [x] 6.1 重写 `water-info-admin/src/stores/aiConversation.ts::loadSession`
    - 先快照 `previousMessages` / `previousSessionId` / `previousSnapshot` / `previousTitle`
    - 调用 `getConversationMessages(sessionId)`，成功时把返回 `messages` 经 `mapServerMessageToChatItem` 映射并按 `timestamp` 升序排序后替换 `messages.value`
    - 成功时同步更新 `currentSessionId` / `sessionTitle` / `snapshot`；重置 `pendingTraces` 与 agent 状态；调用 `persistToLocalStorage`
    - 失败时逐字段回滚到快照（`messages` / `currentSessionId` / `snapshot` / `sessionTitle`），抛出带后端 message 的 `Error`
    - `isLoadingSession` 在 `try/finally` 中正确 toggle
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.4, 4.2_

  - [x] 6.2 为 `loadSession` 成功路径编写属性测试（Property 1）
    - **Property 1: 加载会话的原子性**
    - **Validates: Requirements 1.1, 1.2, 1.3, 2.1**
    - 使用 `@fast-check/vitest` 生成非空 `sessionId`（与当前 `currentSessionId` 不同）与任意 `ConversationDetail`
    - Mock `getConversationMessages`，断言成功后：
      1. `store.currentSessionId === sessionId`
      2. `getConversationMessages` 被调用恰好一次、第一参数严格等于 `sessionId`
      3. `store.messages.length === detail.messages.length`，对应 `content` 相等，`timestamp` 单调不减
    - 标签：`Feature: ai-session-history-resume, Property 1: loadSession atomicity`
    - 至少 100 次迭代
    - _Requirements: 1.1, 1.2, 1.3, 2.1_

  - [x] 6.3 为 `loadSession` 失败路径编写属性测试（Property 6）
    - **Property 6: 加载失败时保留先前状态**
    - **Validates: Requirements 4.2**
    - 使用 `@fast-check/vitest` 生成非空前态 S₀（`currentSessionId` / `messages` / `snapshot` / `sessionTitle`）与任意抛错（4xx / 5xx / NetworkError）的 `getConversationMessages` mock
    - 断言：`loadSession(newSessionId)` 抛错/结束后，store 的四个字段与 S₀ 逐字段相等
    - 标签：`Feature: ai-session-history-resume, Property 6: loadSession failure preservation`
    - 至少 100 次迭代
    - _Requirements: 4.2_

- [x] 7. Frontend: 会话切换收尾（`handleSessionSelect`）
  - [x] 7.1 改造 `water-info-admin/src/views/ai/command/index.vue::handleSessionSelect`
    - 成功时：`startTime.value = new Date().toLocaleTimeString()`；`resetStreamBuffers()`；`reset()`；`store.setDrawerOpen(false)`；`syncRouteSession(newSessionId)`；`await nextTick()` 后 `scrollChatToBottom()`
    - 失败时：捕获 `loadSession` 抛出的 `Error`，调用 `ElMessage.error(err.message || '加载会话失败，请稍后重试')`，不清空视图
    - 当 `newSessionId === store.currentSessionId` 时提前 return，避免重复加载
    - _Requirements: 1.1, 1.4, 1.5, 4.1_

- [x] 8. Frontend: SessionDrawer 键盘可达
  - [x] 8.1 在 `water-info-admin/src/components/SessionDrawer.vue::session-row` 上补齐 ARIA 与键盘事件
    - 根元素增加 `role="button"`、`tabindex="0"`、`:aria-current="item.session_id === currentSessionId ? 'true' : 'false'"`
    - 绑定 `@keyup.enter.prevent="handleSelect(item)"` 与 `@keyup.space.prevent="handleSelect(item)"`
    - 保留原 `@click` 逻辑作为鼠标兜底
    - 确保 `:focus-visible` 状态有可见轮廓（借用 Element Plus focus ring 或自定义）
    - _Requirements: 1.6_

- [x] 9. Frontend: SSE 错误事件与 sendQuery 契约
  - [x] 9.1 扩展 `water-info-admin/src/composables/useAgentStream.ts`（或等价 `handleStreamEvent`）的 `case 'error'` 分支
    - 解析服务端事件中的 `recoverable` 与 `code` 字段
    - 当 `recoverable === false` 时：调用 `store.failAssistant(message, false)`、`ElMessage.error(message)`，并调用 `stop()` 终止当前流
    - 当 `recoverable !== false` 时保持现有降级逻辑（提示重试但不终止）
    - 与后端 Task 3.3 的事件形状对齐（`type/message/code/recoverable`）
    - _Requirements: 4.4, 4.5_

  - [x] 9.2 为 `sendQuery` 编写属性测试（Property 5）
    - **Property 5: Loaded_Session 上发送消息必然携带 `session_id`**
    - **Validates: Requirements 3.1**
    - 使用 `@fast-check/vitest` 生成合法非空 `currentSessionId` 与任意非空 `queryText`
    - Mock `useAgentStream.start(url, payload)`，断言 `payload.sessionId === store.currentSessionId`（严格等价）
    - 覆盖「加载会话后立即发送」的路径：先调用 `loadSession(mockedId)` 成功，再调用 `sendQuery(text)`
    - 标签：`Feature: ai-session-history-resume, Property 5: sendQuery carries session_id`
    - 至少 100 次迭代
    - _Requirements: 3.1_

- [x] 10. Final Checkpoint — 全栈联调
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- 带 `*` 的子任务为可选测试项，跳过不影响核心功能，但建议保留以守护 6 条 Correctness Properties。
- Property 1 / 2 / 5 / 6 用 `@fast-check/vitest` 跑在 `water-info-admin` 前端测试套件中；Property 3 / 4 用 `hypothesis` 跑在 `water-info-ai` 后端测试套件中。
- Requirements 1.4 / 1.5 / 4.3 的 UI 降级行为通过 Task 6.1 + 7.1 + 8.1 的实现直接覆盖；属性不适合生成器化的部分由 Task 7.1 中的例子断言兜底。
- `conversation_messages.metadata` 的 JSONB schema 已在 design.md §1 正式化；若未来字段演进须同步升级 `version` 字段与前后端映射器。
- 后端改造不新增数据库迁移，复用既有 `conversation_messages` / `conversation_snapshots` 表。

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1", "5.1", "8.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "3.2", "5.2", "6.1"] },
    { "id": 2, "tasks": ["1.3", "2.3", "3.3", "6.2", "6.3", "7.1", "9.2"] },
    { "id": 3, "tasks": ["3.4", "9.1"] }
  ]
}
```
