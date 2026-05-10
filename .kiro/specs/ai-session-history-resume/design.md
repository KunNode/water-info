# Design Document

## Overview

本设计打通「点击 Session_Drawer 条目 → Conversation_Store.loadSession → 还原 Reasoning_Chain / Tool_Call_Trace → 基于完整历史续聊 → AI 保留上下文」的端到端链路。

涉及三层改造：
1. **前端状态还原**：扩展 `conversation_messages.metadata` JSONB，前端在 `loadSession` 中把 `reasoning_steps` / `execution_traces` / `tool_calls` 映射回 `ChatMessageItem.reasoning` 与 `traces`。
2. **后端上下文注入**：`/flood/query/stream` 已在用 `session_id` 作为 `thread_id` 进入 LangGraph，但 `memory_loader_node` 返回的 `memory_context` 需要确保每个调用 LLM 的 Agent（Supervisor / Conversation_Assistant / Risk_Assessor / Plan_Generator / Final_Response）都把 `recent_session_messages`、`business_snapshot`、`conversation_summary`、`long_term_memories` 放入 prompt payload。
3. **持久化一致性**：新会话期间写回 `conversation_messages.metadata` 的字段必须与加载时的期望字段对齐，保证「写入什么 → 读出什么 → 前端还原什么」闭环。

## 根因诊断：为什么点击目前"无反应"

代码走查结果：**事件链本身是连通的**，但加载后的 UI 表现让用户感到"没反应"。

| 环节 | 现状 | 证据 |
| --- | --- | --- |
| `SessionDrawer` 点击 → `select` emit | ✅ 已触发 | `components/SessionDrawer.vue::handleSelect(item)` → `emit('select', item.session_id)` |
| `index.vue` 监听 `select` | ✅ 已绑定 | `@select="handleSessionSelect"` |
| `handleSessionSelect` 调用 `store.loadSession` | ✅ 已调用 | `await store.loadSession(newSessionId)` |
| `loadSession` 调用 API | ✅ 已调用 | `getConversationMessages(sessionId)` |
| 消息映射 | ⚠️ 信息丢失 | `stores/aiConversation.ts::loadSession` 只保留 `id/role/content/timestamp/traces`，**丢失 reasoning 思维链**与 **tool_calls 明细**，且 `traces` 从 `m.metadata?.execution_traces` 取但字段没有透传 `phase/tool_name` 等结构 |
| Drawer 关闭 + 焦点跳转 | ❌ 未执行 | `handleSessionSelect` 没有在成功后显式 `store.setDrawerOpen(false)`；抽屉仅靠 `v-model="store.drawerOpen"` 用户手动关 |
| 错误提示 | ❌ 静默失败 | `loadSession` 的 catch 分支只 `console.error` 并 `clearCurrentSession()`，没有 `ElMessage.error`，也没有保留现场 |
| 键盘可达 | ❌ 不支持 | `session-row` 是 `<div @click>`，没有 `tabindex`、没有 `@keyup.enter/space` |

**诊断结论**：功能并非完全不触发，而是"加载后看不见变化"——思维链/工具轨迹没被还原，抽屉没自动关，失败时既不提示也保留不了现场。这四个缺陷叠加让用户认为"点击无效"。

## Architecture

```
┌─────────────────────────── water-info-admin ───────────────────────────┐
│                                                                         │
│  SessionDrawer.vue ──emit('select', session_id)──┐                      │
│                                                   ▼                      │
│  views/ai/command/index.vue::handleSessionSelect(id)                     │
│      └─► store.loadSession(id)                                           │
│             └─► GET /api/v1/conversations/{id}/messages                  │
│             └─► map → ChatMessageItem[] (role/content/reasoning/traces)  │
│             └─► store.setDrawerOpen(false)  ← 新增                       │
│             └─► 滚动视图到底部                                           │
│                                                                         │
│  ChatPanel (sendQuery) ──payload.sessionId = store.currentSessionId──┐  │
│                                                                       │  │
└───────────────────────────────────────────────────────────────────────┼──┘
                                                                        │
                     POST /api/v1/flood/query/stream                    │
                                                                        ▼
┌─────────────────────────── water-info-ai ─────────────────────────────────┐
│  main.py::event_stream()                                                   │
│    ├─ db.ensure_or_create_session(session_id, ...)                         │
│    ├─ _load_session_history(session_id)  # LangGraph checkpoint 或 DB 回放 │
│    ├─ initial_state = {session_id, user_query, messages: history+[user]}  │
│    ├─ flood_response_graph.astream(..., thread_id=session_id)             │
│    │    ├─ memory_loader_node                                              │
│    │    │    └─ MemoryService.load_context(session_id, user_id, query)    │
│    │    │          ├─ db.get_latest_conversation_summary(session_id)       │
│    │    │          ├─ db.get_conversation_snapshot(session_id)             │
│    │    │          ├─ db.get_conversation_messages(session_id, limit=10)   │
│    │    │          └─ db.search_memory_items(namespaces, query)            │
│    │    │    → state.memory_context = MemoryContext.to_prompt_context()    │
│    │    ├─ supervisor_node       (prompt: memory_context)                  │
│    │    ├─ conversation_assistant (prompt: memory_context)                 │
│    │    ├─ risk_assessor / plan_generator / final_response (prompt: ctx)   │
│    │    └─ memory_writer_node                                              │
│    ├─ save_conversation_message("user", ...)                               │
│    ├─ save_conversation_message("assistant", "", status="streaming")       │
│    └─ update_message_content(id, final, metadata={reasoning_steps,        │
│                                                   execution_traces,        │
│                                                   tool_calls})             │
└───────────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. 消息元数据 JSONB Schema（关键契约）

`conversation_messages.metadata` 在本特性中被正式化为下列结构。后端写入、后端读取、前端映射、前端展示全部遵循此 schema。

```json
{
  "reasoning_steps": [
    {
      "id": "thought-1700000000-ab12c",
      "kind": "thought" | "tool",
      "title": "正在评估风险等级",
      "content": "依据 data_summary 中三站连续超限...",
      "status": "pending" | "running" | "success" | "error",
      "started_at": 1700000000000,
      "ended_at": 1700000002500,
      "duration_ms": 2500,
      "tool": {
        "name": "get_station_overview",
        "display_name": "查询站点总览",
        "input_summary": "已接收 station_code、limit 等查询条件",
        "result_summary": "返回 3 条最新观测"
      }
    }
  ],
  "execution_traces": [
    {
      "phase": "data_query" | "risk_assessment" | "plan_generation" | "final_response" | ...,
      "status": "completed" | "failed" | "running",
      "title": "意图识别: plan_generation",
      "detail": "焦点站点: 翠屏湖",
      "tool_name": "get_station_overview" | null,
      "metadata": {
        "duration_ms": 120,
        "input_summary": "…",
        "output_summary": "…"
      }
    }
  ],
  "tool_calls": [
    {
      "tool_call_id": "tool-1700000000-xx",
      "tool_name": "get_active_alarms",
      "arguments": { "station_code": "FRONT-01" },
      "result": { "count": 3 },
      "error": null,
      "duration_ms": 450
    }
  ],
  "agent": "risk_assessor",
  "session_title_hint": "翠屏湖风险研判",
  "version": 1
}
```

约束：
- 所有字段均可选；缺失或为空数组即表示该消息没有对应数据，前端必须优雅降级为空视图，不得报错。
- 时间戳以毫秒为单位的 UNIX 时间（与前端 `Date.now()` 对齐）。
- `reasoning_steps` 是前端展示"思维链"的单一事实源；`execution_traces` 是"执行轨迹"面板的来源；`tool_calls` 留给审计/调试展开（当前版本可由 `reasoning_steps[].tool` 承载，但单独保留能在调试面板中按原样展示参数/返回）。
- `version=1` 便于后续演进。

### 2. 前端：`stores/aiConversation.ts::loadSession` 映射

```typescript
async function loadSession(sessionId: string) {
  if (!sessionId) {
    clearCurrentSession()
    return
  }

  // ── Preserve fallback state for graceful failure (Req 4.2) ─────────
  const previousMessages = messages.value
  const previousSessionId = currentSessionId.value
  const previousSnapshot = snapshot.value
  const previousTitle = sessionTitle.value

  isLoadingSession.value = true
  try {
    const res = await getConversationMessages(sessionId)
    const detail = res.data

    currentSessionId.value = sessionId
    sessionTitle.value = detail?.title ?? ''
    snapshot.value = detail?.snapshot ?? null
    messages.value = (detail?.messages ?? []).map(mapServerMessageToChatItem)

    // Explicit ordering guard (Req 2.1)
    messages.value.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())

    pendingTraces.value = []
    resetAgentStatus()
    persistToLocalStorage()
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    console.error('[AI Store] Failed to load session:', e)

    // Requirement 4.2: keep prior view on failure
    messages.value = previousMessages
    currentSessionId.value = previousSessionId
    snapshot.value = previousSnapshot
    sessionTitle.value = previousTitle

    throw new Error(`加载会话失败：${msg}`)
  } finally {
    isLoadingSession.value = false
  }
}

function mapServerMessageToChatItem(m: ConversationMessage): ChatMessageItem {
  const meta = m.metadata ?? {}
  const isAssistant = m.role === 'assistant'
  const timestamp = m.created_at ? new Date(m.created_at) : new Date()

  const reasoning = isAssistant && Array.isArray(meta.reasoning_steps) && meta.reasoning_steps.length
    ? deserializeReasoningState(meta.reasoning_steps, timestamp)
    : undefined

  const traces = Array.isArray(meta.execution_traces) && meta.execution_traces.length
    ? meta.execution_traces.map(deserializeExecutionTrace)
    : undefined

  return {
    id: m.id,
    role: m.role as 'user' | 'assistant',
    content: m.content,
    timestamp,
    status: isAssistant ? 'done' : undefined,
    reasoning,
    answer: isAssistant ? { status: 'done', content: m.content } : undefined,
    traces,
  }
}

function deserializeReasoningState(steps: RawStep[], ts: Date): ReasoningState {
  const hydrated: ReasoningStep[] = steps.map(s => ({
    id: String(s.id ?? `hist-${ts.getTime()}-${Math.random().toString(36).slice(2, 7)}`),
    kind: (s.kind === 'tool' ? 'tool' : 'thought'),
    title: String(s.title ?? ''),
    content: String(s.content ?? ''),
    status: s.status === 'error' ? 'error' : 'success', // history is always terminal
    startedAt: Number(s.started_at ?? ts.getTime()),
    endedAt: Number(s.ended_at ?? ts.getTime()),
    durationMs: typeof s.duration_ms === 'number' ? s.duration_ms : undefined,
    tool: s.tool ? {
      name: String(s.tool.name ?? ''),
      displayName: String(s.tool.display_name ?? s.tool.name ?? ''),
      inputSummary: s.tool.input_summary,
      resultSummary: s.tool.result_summary,
    } : undefined,
    isDefaultExpand: false, // history: collapsed by default
  }))
  const startedAt = hydrated[0]?.startedAt ?? ts.getTime()
  const endedAt = hydrated[hydrated.length - 1]?.endedAt ?? ts.getTime()
  return {
    status: 'done',
    title: `历史思考（共 ${hydrated.length} 步）`,
    expanded: false,
    startedAt,
    endedAt,
    elapsedMs: endedAt - startedAt,
    steps: hydrated,
  }
}
```

### 3. 前端：`views/ai/command/index.vue::handleSessionSelect` 收尾

```typescript
async function handleSessionSelect(newSessionId: string) {
  if (!newSessionId || newSessionId === store.currentSessionId) return

  try {
    await store.loadSession(newSessionId)
    startTime.value = new Date().toLocaleTimeString()
    resetStreamBuffers()
    reset()
    store.setDrawerOpen(false)                          // Req 1.4: auto-close drawer
    syncRouteSession(newSessionId)
    await nextTick()
    scrollChatToBottom()                                 // Req 1.4: scroll to latest
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    ElMessage.error(msg || '加载会话失败，请稍后重试')   // Req 4.1
  }
}
```

### 4. 前端：`SessionDrawer.vue` 键盘可达（Req 1.6）

```vue
<div
  v-for="item in conversations"
  :key="item.session_id"
  class="session-row"
  role="button"
  tabindex="0"
  :aria-current="item.session_id === currentSessionId ? 'true' : 'false'"
  @click="handleSelect(item)"
  @keyup.enter.prevent="handleSelect(item)"
  @keyup.space.prevent="handleSelect(item)"
>
  …
</div>
```

### 5. 前端：SSE 错误事件处理（Req 4.5）

`useAgentStream` 已经暴露 `onEvent`，`handleStreamEvent` 的 `case 'error'` 分支已存在。本设计将：
- 后端在加载历史上下文失败时 `yield _event_line({"type": "error", "message": "...", "recoverable": false, "code": "memory_load_failed"})` 然后终止流。
- 前端 `handleRecoverableError(message, recoverable)`：当 `recoverable=false` 时调用 `store.failAssistant(msg, false)` 并 `ElMessage.error(msg)`，同时 `stop()` 当前流。

### 6. 后端：`MemoryService.load_context` 的完整性保证（Req 3.2 / 3.3）

当前实现已经同时读取 `summary / snapshot / recent_messages / memory_items`。本特性补强：

```python
# memory/service.py - load_context (incremental refinement)
async def load_context(self, *, user_id: str = "", session_id: str, query: str, ...):
    db = get_db_service()
    summary, snapshot, memories = "", None, []
    recent_session_messages: list[dict[str, str]] = []

    try:
        summary_row = await db.get_latest_conversation_summary(session_id)
        summary = str(summary_row.get("summary") or "") if summary_row else ""
    except Exception as exc:
        logger.warning("[%s] summary load failed: %s", session_id, exc)
        raise MemoryLoadError("summary") from exc   # NEW: propagate fatal load failures

    try:
        raw_snapshot = await db.get_conversation_snapshot(session_id)
        snapshot = _normalize_snapshot(raw_snapshot) if raw_snapshot else None
    except Exception as exc:
        logger.warning("[%s] snapshot load failed: %s", session_id, exc)
        raise MemoryLoadError("snapshot") from exc

    # Req 3.2: *always* attempt to load DB messages, up to CONTEXT_HISTORY_LIMIT,
    # even when recent_messages were pre-populated by the router, so that a
    # session loaded via click-to-resume has the same payload as live streaming.
    try:
        rows = await db.get_conversation_messages(session_id, limit=CONTEXT_HISTORY_LIMIT)
        db_messages = _normalize_chat_messages(rows, limit=CONTEXT_HISTORY_LIMIT)
        if db_messages:
            recent_session_messages = db_messages
    except Exception as exc:
        logger.warning("[%s] recent messages load failed: %s", session_id, exc)
        raise MemoryLoadError("conversation_messages") from exc

    # … embedding search / store search unchanged, but non-fatal …

    return MemoryContext(
        summary=summary,
        recent_messages=recent_session_messages,
        memories=memories,
        snapshot=snapshot,
    )
```

关键点：
- `CONTEXT_HISTORY_LIMIT` 由 `settings.memory_context_history_limit` 控制（默认 20 条，可配置）。
- 新增 `MemoryLoadError`：当"会话一定存在但数据库读失败"属于不可降级错误，向 `event_stream` 冒泡（对应 Req 4.4）。非关键数据（`memory_items` / `conversation_summary` 为空）继续降级。
- `memory_loader_node` 捕获 `MemoryLoadError` 后返回 `{"memory_context": {}, "error": "memory_load_failed: ...", "next_agent": "__end__"}`，同时流层将其映射为 `type=error` 事件。

### 7. 后端：每个 Agent 都持有 memory context（Req 3.4）

走查确认以下节点已在 prompt 里携带 `memory_context`：
- `agents/supervisor.py::supervisor_node`（`"memory_context": state.get("memory_context", {})`）
- `agents/conversation_assistant.py`（`"memory_context": to_plain_data(memory_context)`）
- `agents/risk_assessor.py`（`"memory_context": to_plain_data(state.get("memory_context", {}))`）
- `agents/plan_generator.py`（同上）
- `agents/final_response.py`（同上）

**缺口**：`data_analyst`、`resource_dispatcher`、`notification`、`execution_monitor`、`knowledge_retriever` 当前并未在 prompt 里引用 `memory_context`。对 Loaded_Session 续聊而言，这几个节点即便不需要自然语言级别的历史上下文，也必须至少获取 `business_snapshot.plan_info`、`risk_assessment` 历史值，以免在"基于上轮结论继续操作"时丢失上下文。

本设计引入一个助手 `_session_context_payload(state)`，所有 LLM 节点必须调用它构造 prompt：

```python
# app/agents/_prompt.py  (NEW helper module)
def session_context_payload(state: dict) -> dict:
    """Canonical memory payload required for every LLM-invoking agent."""
    return {
        "conversation_summary": state.get("memory_context", {}).get("conversation_summary", ""),
        "recent_session_messages": state.get("memory_context", {}).get("recent_session_messages", []),
        "business_snapshot": state.get("memory_context", {}).get("business_snapshot", {}),
        "long_term_memories": state.get("memory_context", {}).get("long_term_memories", []),
    }
```

所有 LLM 节点在构造 prompt JSON 时都必须把 `"memory_context": session_context_payload(state)` 作为顶层键写入。这成为一个被属性测试强制的全局不变式（见 Property 4）。

### 8. 后端：持久化契约对齐（Req 3.6）

`main.py::event_stream()` 已经在最后一步把 `execution_traces` 写入 metadata。本设计把写入扩展为完整 schema，使用 graph 最终 state 中的字段：

```python
# main.py - in event_stream, after loop ends
if final_state:
    final_response = final_state.get("final_response") or accumulated_response or "处理完成"
    reasoning_steps = _reasoning_steps_from_final_state(final_state)
    tool_calls = _tool_calls_from_traces(final_state.get("execution_traces") or [])
    trace_metadata = {
        "version": 1,
        "agent": final_state.get("current_agent") or "final_response",
        "reasoning_steps": reasoning_steps,
        "execution_traces": final_state.get("execution_traces") or [],
        "tool_calls": tool_calls,
    }
    await db.update_message_content(
        assistant_msg_id,
        final_response,
        status="completed",
        metadata=trace_metadata,
    )
```

`_reasoning_steps_from_final_state` 在现有 `execution_traces` 基础上构造与前端 `ReasoningStep` 结构一致的数组（保证 `loadSession` 的 `deserializeReasoningState` 能无损还原）。

### 9. 前端：发送消息时携带 session_id（Req 3.1）

已实现：`sendQuery` 中 `if (store.currentSessionId) payload.sessionId = store.currentSessionId`。本设计不改变该行为，只要求属性测试覆盖"加载后立即发送"的路径。

## Data Models

### `conversation_messages` 表（已存在）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | bigint PK | 自增 |
| session_id | text FK | 指向 conversation_session |
| role | text | user / assistant |
| content | text | 最终文本 |
| message_type | text | chat |
| status | text | streaming / completed / failed |
| metadata | jsonb | 按第 1 节 schema |
| created_at | timestamptz | 入库时间（排序依据） |

### `conversation_snapshots` 表（已存在）

MemoryContext 读取 `risk_level / plan_info / agent_status_summary / query_count`，不做 schema 变更。

### `ConversationDetailResponse`（后端→前端）

保持现有字段：`session_id / title / messages[] / snapshot / has_more / created_at`。`messages[].metadata` 按第 1 节 schema，前端强制信任版本字段。

## Error Handling

| 失败点 | 行为 | 验收项 |
| --- | --- | --- |
| `getConversationMessages` 非 2xx | `loadSession` 恢复先前 `messages`/`currentSessionId`，抛错；`handleSessionSelect` `ElMessage.error` | Req 4.1 / 4.2 |
| 后端 `get_conversation_messages` 异常 | HTTPException 500 + 日志 | Req 4.1 |
| 后端 `MemoryService.load_context` 失败 | 抛 `MemoryLoadError` → `memory_loader_node` 返回错误状态 → `event_stream` 发送 `{type: "error", recoverable: false, message, code}` → 终止流 | Req 4.4 |
| 空消息列表 | 前端正常渲染空态（`messages=[]`, `isNewSession=false` 但 `currentSessionId` 非空），允许 sendQuery 带此 ID | Req 4.3 |
| SSE `error` 事件 | `handleStreamEvent` 的 `case 'error'` 分支；`recoverable=false` 时调用 `store.failAssistant` + `ElMessage.error` + `stop()` | Req 4.5 |
| 键盘交互失败（浏览器不支持） | 仍有鼠标 click 兜底 | Req 1.6 |

## Testing Strategy

- **单元测试**：`mapServerMessageToChatItem` / `deserializeReasoningState` / `session_context_payload` 等纯函数走 Vitest / pytest。
- **属性测试（PBT）**：下方 Correctness Properties 中每条以 `**Validates: Requirements X.Y**` 标注，最少 100 次迭代，使用 `@fast-check/vitest` 与 `hypothesis`。
  - 前端工具：`fast-check`，标签 `Feature: ai-session-history-resume, Property N: ...`
  - 后端工具：`hypothesis`，同样的标签约定
- **集成测试**：1–2 条真实 LangGraph 调用的 smoke case 覆盖 Req 3.5（LLM 在加载后的历史基础上生成回复时能引用历史实体），不适合做 100 次 PBT 迭代。

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

在写入属性之前，对 prework 中 13 条 PROPERTY 做一次冗余合并：

- 1.1（currentSessionId 更新）、1.2（API 调用）、1.3（messages 替换）都是 `loadSession` 这一原子操作的组成部分。合并为 **Property 1：加载会话原子性**。
- 2.1（顺序+字段保留）、2.2（reasoning 还原）、2.3（traces 还原）、2.4（整体 round-trip）在「写入 metadata → 读取 → 映射」这条链上彼此蕴含。合并为 **Property 2：消息持久化 round-trip**，并以 Req 3.6 为写入端。
- 3.2（读取全部历史）与 3.3（读取 snapshot + summary）属于 `load_context` 的返回完整性。合并为 **Property 3：加载上下文完整性**。
- 3.4（每个 Agent 都携带 memory_context）独立保留，作为全局不变式 **Property 4**。
- 3.1（发送携带 sessionId）独立保留为 **Property 5**，体量小但容易回归。
- 4.2（失败时保留前态）独立保留为 **Property 6**。

最终 6 条属性，加 2 个 example 测试（1.4/1.5/1.6 UI 行为 与 4.1/4.3/4.5 错误提示）与 1 个 integration smoke（3.5 LLM 引用能力）。

### Property 1: 加载会话的原子性

*For any* 非空 `sessionId` 且不等于当前 `currentSessionId`，以及任意由 Messages_API 返回的 `ConversationDetail { messages: Message[], snapshot }`，在调用 `store.loadSession(sessionId)` 成功返回后，以下三项必须同时成立：
1. `store.currentSessionId === sessionId`
2. 存在且仅有一次对 `getConversationMessages(sessionId)` 的调用且第一参数等于该 `sessionId`
3. `store.messages.length === messages.length` 且 `store.messages[i].content === messages[i].content` 且 `store.messages[i].timestamp` 单调不减

**Validates: Requirements 1.1, 1.2, 1.3, 2.1**

### Property 2: 消息持久化与还原 round-trip

*For any* 生成的合法 `reasoning_steps[]` / `execution_traces[]` / `tool_calls[]`（含空数组、缺字段、混合 kind=thought|tool），当后端以该 metadata 调用 `save_conversation_message` 或 `update_message_content` 写入，随后 `get_conversation_messages` 读出并由前端 `mapServerMessageToChatItem` 映射时，得到的 `ChatMessageItem` 必须满足：
- 若输入 `reasoning_steps` 非空 → `output.reasoning.steps.length === input.reasoning_steps.length` 且每一步的 `title/content/kind/status/tool.name` 与输入等价
- 若输入 `execution_traces` 非空 → `output.traces.length === input.execution_traces.length` 且 `phase/status/title/tool_name` 与输入等价
- 若两者均为空 → `output.reasoning === undefined` 且 `output.traces === undefined`（不抛错、不渲染空区域）

**Validates: Requirements 2.2, 2.3, 2.4, 2.5, 3.6**

### Property 3: `MemoryService.load_context` 完整性

*For any* 已存在的 `session_id`，若 `conversation_messages` 中该会话包含 N（0 ≤ N ≤ CONTEXT_HISTORY_LIMIT）条 `status='completed'` 且 `role ∈ {user, assistant}` 的消息，并存在可选的 `conversation_snapshots` 行与 `conversation_summary` 行，则 `load_context(session_id=..., query=..., user_id=...)` 的返回值必须满足：
- `len(result.recent_messages)` 等于过滤后 DB 中属于该 session_id 的已完成消息数且顺序按 `id` 升序
- `result.recent_messages` 中每条 `role ∈ {user, assistant}`、`content` 非空
- 若快照行存在 → `result.snapshot.session_id == session_id` 且 `risk_level / plan_info / query_count` 来源于该行
- 若摘要行存在 → `result.summary` 等于最新摘要的 `summary` 字段

**Validates: Requirements 3.2, 3.3**

### Property 4: 每个 LLM Agent 的 prompt 都包含 memory_context

*For any* 非空 `memory_context`（`recent_session_messages / business_snapshot / conversation_summary / long_term_memories` 中至少一项非空），在 `flood_response_graph.astream(initial_state_with_memory_context, thread_id=session_id)` 的完整执行中，以下每一个被实际调用到的节点构造 prompt 时，都必须把 `memory_context`（或 `session_context_payload(state)` 的返回）作为顶层键放入 LLM 请求 payload：
`supervisor`, `conversation_assistant`, `risk_assessor`, `plan_generator`, `final_response`。

**Validates: Requirements 3.4**

### Property 5: 在 Loaded_Session 上发送消息时必然携带 session_id

*For any* `currentSessionId` 为合法非空字符串的 Conversation_Store 状态，以及任意非空 `queryText`，调用 `sendQuery(queryText)` 后，传递给 `useAgentStream.start(url, payload)` 的 `payload.sessionId` 必须严格等于 `store.currentSessionId`。

**Validates: Requirements 3.1**

### Property 6: 加载失败时保留先前状态

*For any* 非空 `store.currentSessionId` / `store.messages` 的 Conversation_Store 状态（状态 S₀），以及任意因 API 抛错（4xx/5xx/网络错误）而失败的 `loadSession(newSessionId)` 调用，调用返回/抛错之后 Conversation_Store 的 `currentSessionId`、`messages`、`snapshot`、`sessionTitle` 必须与 S₀ 逐字段相等。

**Validates: Requirements 4.2**
