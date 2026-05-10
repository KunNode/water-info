/**
 * AI Conversation Store
 *
 * Centralized state management for AI conversation functionality.
 * Backend database is the single source of truth - this store only holds
 * transient UI state and caches server data for reactivity.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ConversationItem, ConversationMessage, ConversationSnapshot } from '@/types'
import type { AgentMessageStatus, AssistantAnswerState, ReasoningState, ReasoningStep } from '@/types/agentStream'
import {
  listConversations,
  getConversation,
  getConversationMessages,
  deleteConversation as apiDeleteConversation,
  renameConversation as apiRenameConversation,
} from '@/api/flood'

export interface ExecutionTrace {
  phase: string
  status: string
  title: string
  detail?: string
  tool_name?: string
  metadata?: Record<string, unknown>
  timestamp?: Date
}

// ── Raw shapes from `conversation_messages.metadata` JSONB (contract with backend) ──
export interface RawReasoningTool {
  name?: unknown
  display_name?: unknown
  input_summary?: unknown
  result_summary?: unknown
}

export interface RawReasoningStep {
  id?: unknown
  kind?: unknown
  title?: unknown
  content?: unknown
  status?: unknown
  started_at?: unknown
  ended_at?: unknown
  duration_ms?: unknown
  tool?: RawReasoningTool | null
}

export interface RawExecutionTrace {
  phase?: unknown
  status?: unknown
  title?: unknown
  detail?: unknown
  tool_name?: unknown
  metadata?: unknown
}

export interface ChatMessageItem {
  id?: number | string
  role: 'user' | 'assistant' | 'thinking' | 'agent'
  content: string
  timestamp: Date
  status?: AgentMessageStatus
  reasoning?: ReasoningState
  answer?: AssistantAnswerState
  error?: string
  agent?: string
  agentStatus?: 'typing' | 'done' | 'pending'
  traces?: ExecutionTrace[]
}

export interface PlanInfo {
  name: string
  status: string
  total: number
  completed: number
  failed: number
}

const LOCAL_STORAGE_KEYS = {
  CURRENT_SESSION_ID: 'fm-ai-active-session-id',
  LEGACY_CURRENT_SESSION_ID: 'water_ai_current_session_id',
  INPUT_DRAFT: 'water_ai_input_draft',
  DRAWER_OPEN: 'water_ai_drawer_open',
}

// ───────────────────────────────────────────────────────────────────
// Server → client message mapping (metadata JSONB schema v1)
// See design.md §1 for the canonical shape. These helpers MUST NOT
// render empty shells when reasoning/traces data is absent: a missing
// `reasoning_steps` or `execution_traces` key yields `undefined`.
// ───────────────────────────────────────────────────────────────────

/**
 * Hydrate a single execution trace entry. Passes `phase/status/title/detail/
 * tool_name/metadata` through verbatim; coerces to strings/objects so that
 * downstream consumers can rely on field types even when the server sends
 * malformed rows.
 */
export function deserializeExecutionTrace(raw: RawExecutionTrace): ExecutionTrace {
  const trace: ExecutionTrace = {
    phase: typeof raw.phase === 'string' ? raw.phase : String(raw.phase ?? ''),
    status: typeof raw.status === 'string' ? raw.status : String(raw.status ?? ''),
    title: typeof raw.title === 'string' ? raw.title : String(raw.title ?? ''),
  }
  if (raw.detail !== undefined && raw.detail !== null) {
    trace.detail = typeof raw.detail === 'string' ? raw.detail : String(raw.detail)
  }
  if (raw.tool_name !== undefined && raw.tool_name !== null) {
    trace.tool_name = typeof raw.tool_name === 'string' ? raw.tool_name : String(raw.tool_name)
  }
  if (raw.metadata && typeof raw.metadata === 'object') {
    trace.metadata = raw.metadata as Record<string, unknown>
  }
  return trace
}

/**
 * Hydrate the reasoning chain for a historical assistant message.
 *
 * In history mode (i.e. re-loading a past session from `loadSession`):
 * - `status` is uniformly `'success'` — every step is terminal by definition
 *   because the assistant already finished speaking. `'error'` is preserved
 *   only when the server explicitly recorded it, so partially-failed runs
 *   still show an error marker.
 * - The outer `ReasoningState.expanded` is `false` (collapsed by default).
 * - Each step's `isDefaultExpand` is `false` (collapsed by default).
 *
 * `ts` is the message's `created_at` timestamp, used as a fallback for
 * `started_at`/`ended_at` when the server didn't record them.
 */
export function deserializeReasoningState(
  steps: RawReasoningStep[],
  ts: Date,
): ReasoningState {
  const tsMs = ts.getTime()
  const hydrated: ReasoningStep[] = steps.map((s, idx) => {
    const kind: ReasoningStep['kind'] = s.kind === 'tool' ? 'tool' : 'thought'
    const rawStatus = typeof s.status === 'string' ? s.status : ''
    // history is always terminal: success, unless the server preserved an error
    const status: ReasoningStep['status'] = rawStatus === 'error' ? 'error' : 'success'

    const startedAt = typeof s.started_at === 'number' && Number.isFinite(s.started_at)
      ? s.started_at
      : tsMs
    const endedAtCandidate = typeof s.ended_at === 'number' && Number.isFinite(s.ended_at)
      ? s.ended_at
      : undefined
    const durationCandidate = typeof s.duration_ms === 'number' && Number.isFinite(s.duration_ms)
      ? s.duration_ms
      : undefined

    const id = typeof s.id === 'string' && s.id.length
      ? s.id
      : typeof s.id === 'number'
        ? String(s.id)
        : `hist-${tsMs}-${idx}`

    const step: ReasoningStep = {
      id,
      kind,
      title: typeof s.title === 'string' ? s.title : String(s.title ?? ''),
      content: typeof s.content === 'string' ? s.content : String(s.content ?? ''),
      status,
      startedAt,
      isDefaultExpand: false,
    }
    if (endedAtCandidate !== undefined) step.endedAt = endedAtCandidate
    if (durationCandidate !== undefined) step.durationMs = durationCandidate

    if (s.tool && typeof s.tool === 'object') {
      const toolName = typeof s.tool.name === 'string' ? s.tool.name : String(s.tool.name ?? '')
      step.tool = {
        name: toolName,
        displayName: typeof s.tool.display_name === 'string' && s.tool.display_name.length
          ? s.tool.display_name
          : toolName,
        inputSummary: typeof s.tool.input_summary === 'string' ? s.tool.input_summary : undefined,
        resultSummary: typeof s.tool.result_summary === 'string' ? s.tool.result_summary : undefined,
      }
    }

    return step
  })

  const startedAt = hydrated[0]?.startedAt ?? tsMs
  const endedAt = hydrated.reduce<number>((acc, step) => {
    const candidate = step.endedAt ?? step.startedAt
    return candidate > acc ? candidate : acc
  }, startedAt)

  return {
    status: 'done',
    title: `历史思考（共 ${hydrated.length} 步）`,
    expanded: false,
    startedAt,
    endedAt,
    elapsedMs: Math.max(0, endedAt - startedAt),
    steps: hydrated,
  }
}

/**
 * Map one server-side `ConversationMessage` to the client `ChatMessageItem`.
 *
 * Invariants enforced by this function (see requirements.md §2):
 * - `id`/`role`/`content` passed through; `timestamp` parsed from `created_at`
 *   (falling back to `new Date()` when absent).
 * - `status` is `'done'` for assistant messages (historical view) and
 *   `undefined` for user messages.
 * - `answer` is populated only for assistant messages, mirroring `content`
 *   so downstream renderers can treat history and live responses uniformly.
 * - `reasoning` is populated ONLY when `role === 'assistant'` AND
 *   `metadata.reasoning_steps` is a non-empty array. Otherwise `undefined`.
 * - `traces` is populated ONLY when `metadata.execution_traces` is a
 *   non-empty array. Otherwise `undefined`.
 */
export function mapServerMessageToChatItem(m: ConversationMessage): ChatMessageItem {
  const meta = (m.metadata ?? {}) as Record<string, unknown>
  const isAssistant = m.role === 'assistant'
  const timestamp = m.created_at ? new Date(m.created_at) : new Date()

  const rawReasoning = meta.reasoning_steps
  const reasoning = isAssistant && Array.isArray(rawReasoning) && rawReasoning.length > 0
    ? deserializeReasoningState(rawReasoning as RawReasoningStep[], timestamp)
    : undefined

  const rawTraces = meta.execution_traces
  const traces = Array.isArray(rawTraces) && rawTraces.length > 0
    ? (rawTraces as RawExecutionTrace[]).map(deserializeExecutionTrace)
    : undefined

  const item: ChatMessageItem = {
    id: m.id,
    role: m.role as 'user' | 'assistant',
    content: m.content,
    timestamp,
  }

  if (isAssistant) {
    item.status = 'done'
    item.answer = { status: 'done', content: m.content }
  }
  if (reasoning) item.reasoning = reasoning
  if (traces) item.traces = traces

  return item
}

export const useAiConversationStore = defineStore('aiConversation', () => {
  // ── Session list (from server) ────────────────────────────────────
  const sessions = ref<ConversationItem[]>([])
  const sessionsLoading = ref(false)

  // ── Current session state ─────────────────────────────────────────
  const currentSessionId = ref<string>('')
  const messages = ref<ChatMessageItem[]>([])
  const snapshot = ref<ConversationSnapshot | null>(null)
  const sessionTitle = ref('')
  const isLoadingSession = ref(false)

  // ── Transient UI state (persisted to localStorage) ────────────────
  const inputDraft = ref('')
  const drawerOpen = ref(false)

  // ── Execution trace accumulator (transient, attached to visible responses) ──
  const pendingTraces = ref<ExecutionTrace[]>([])

  // ── Agent timeline state (transient, not persisted) ───────────────
  const agentStatus = ref<Record<string, string>>({
    supervisor: 'pending',
    data_analyst: 'pending',
    risk_assessor: 'pending',
    plan_generator: 'pending',
    knowledge_retriever: 'pending',
    resource_dispatcher: 'pending',
    notification: 'pending',
  })

  // ── Derived state ─────────────────────────────────────────────────
  const riskLevel = computed(() => snapshot.value?.risk_level ?? 'none')
  const queryCount = computed(() => snapshot.value?.query_count ?? 0)
  const planInfo = computed<PlanInfo | null>(() => {
    const info = snapshot.value?.plan_info
    if (!info || !info.plan_id) return null
    return {
      name: info.plan_name ?? '',
      status: info.status ?? '',
      total: info.actions_count ?? 0,
      completed: 0,
      failed: 0,
    }
  })

  const isNewSession = computed(() => !currentSessionId.value)

  // ── Initialize from localStorage ──────────────────────────────────
  function initFromLocalStorage() {
    const savedSessionId = localStorage.getItem(LOCAL_STORAGE_KEYS.CURRENT_SESSION_ID)
      || localStorage.getItem(LOCAL_STORAGE_KEYS.LEGACY_CURRENT_SESSION_ID)
    const savedDraft = localStorage.getItem(LOCAL_STORAGE_KEYS.INPUT_DRAFT)
    const savedDrawerOpen = localStorage.getItem(LOCAL_STORAGE_KEYS.DRAWER_OPEN)

    if (savedSessionId) currentSessionId.value = savedSessionId
    if (savedDraft) inputDraft.value = savedDraft
    if (savedDrawerOpen) drawerOpen.value = savedDrawerOpen === 'true'
  }

  // ── Persist minimal state to localStorage ─────────────────────────
  function persistToLocalStorage() {
    if (currentSessionId.value) {
      localStorage.setItem(LOCAL_STORAGE_KEYS.CURRENT_SESSION_ID, currentSessionId.value)
    } else {
      localStorage.removeItem(LOCAL_STORAGE_KEYS.CURRENT_SESSION_ID)
    }
    localStorage.removeItem(LOCAL_STORAGE_KEYS.LEGACY_CURRENT_SESSION_ID)
    localStorage.setItem(LOCAL_STORAGE_KEYS.INPUT_DRAFT, inputDraft.value)
    localStorage.setItem(LOCAL_STORAGE_KEYS.DRAWER_OPEN, String(drawerOpen.value))
  }

  // ── Fetch session list from server ────────────────────────────────
  async function fetchSessions() {
    sessionsLoading.value = true
    try {
      const res = await listConversations({ limit: 50, offset: 0 })
      sessions.value = res.data ?? []
    } catch (e) {
      console.error('[AI Store] Failed to fetch sessions:', e)
      sessions.value = []
    } finally {
      sessionsLoading.value = false
    }
  }

  // ── Load a session from server (messages + snapshot) ──────────────
  //
  // Atomicity & failure semantics (see design.md §2 / requirements §4.2):
  // - Snapshot the prior `messages` / `currentSessionId` / `snapshot` /
  //   `sessionTitle` BEFORE issuing the network call.
  // - On success: map server messages through `mapServerMessageToChatItem`,
  //   sort by `timestamp` ascending, replace the reactive state atomically,
  //   reset transient UI state (`pendingTraces`, agent status), then persist.
  // - On failure: restore all four fields from the snapshot field-by-field
  //   and rethrow a new `Error` carrying the backend message so callers
  //   (e.g. `handleSessionSelect`) can surface it via `ElMessage.error`.
  // - `isLoadingSession` is toggled in `try/finally` so the UI spinner
  //   always clears, regardless of outcome.
  async function loadSession(sessionId: string) {
    if (!sessionId) {
      clearCurrentSession()
      return
    }

    // Snapshot prior state for rollback on failure.
    const previousMessages = messages.value
    const previousSessionId = currentSessionId.value
    const previousSnapshot = snapshot.value
    const previousTitle = sessionTitle.value

    isLoadingSession.value = true
    try {
      const res = await getConversationMessages(sessionId)
      const detail = res.data

      const mapped = (detail?.messages ?? []).map(mapServerMessageToChatItem)
      // Explicit ordering guard — server already orders by created_at asc,
      // but sorting client-side defends against any reordering upstream.
      mapped.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())

      messages.value = mapped
      currentSessionId.value = sessionId
      sessionTitle.value = detail?.title ?? ''
      snapshot.value = detail?.snapshot ?? null

      pendingTraces.value = []
      resetAgentStatus()
      persistToLocalStorage()
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      console.error('[AI Store] Failed to load session:', e)

      // Rollback each tracked field to the pre-call snapshot (Req 4.2).
      messages.value = previousMessages
      currentSessionId.value = previousSessionId
      snapshot.value = previousSnapshot
      sessionTitle.value = previousTitle

      throw new Error(`加载会话失败：${msg}`)
    } finally {
      isLoadingSession.value = false
    }
  }

  // ── Start a new session (draft mode - no server call yet) ─────────
  function startNewSession() {
    currentSessionId.value = ''
    sessionTitle.value = ''
    messages.value = []
    snapshot.value = null
    pendingTraces.value = []
    resetAgentStatus()
    persistToLocalStorage()
  }

  // ── Clear current session state ───────────────────────────────────
  function clearCurrentSession() {
    currentSessionId.value = ''
    sessionTitle.value = ''
    messages.value = []
    snapshot.value = null
    pendingTraces.value = []
    resetAgentStatus()
    persistToLocalStorage()
  }

  // ── Set session ID (called after SSE session_init event) ──────────
  function setSessionId(sessionId: string) {
    currentSessionId.value = sessionId
    persistToLocalStorage()
  }

  // ── Update snapshot from server events ────────────────────────────
  function updateSnapshot(partial: Partial<ConversationSnapshot>) {
    snapshot.value = {
      risk_level: partial.risk_level ?? snapshot.value?.risk_level ?? 'none',
      plan_info: partial.plan_info ?? snapshot.value?.plan_info ?? null,
      agent_status_summary: partial.agent_status_summary ?? snapshot.value?.agent_status_summary ?? null,
      query_count: partial.query_count ?? (snapshot.value?.query_count ?? 0) + 1,
    }
  }

  // ── Agent status management ───────────────────────────────────────
  function resetAgentStatus() {
    agentStatus.value = {
      supervisor: 'pending',
      data_analyst: 'pending',
      risk_assessor: 'pending',
      plan_generator: 'pending',
      knowledge_retriever: 'pending',
      resource_dispatcher: 'pending',
      notification: 'pending',
    }
  }

  function setAgentStatus(agent: string, status: string) {
    agentStatus.value[agent] = status
  }

  function finalizeAgentStatuses() {
    Object.keys(agentStatus.value).forEach(key => {
      if (agentStatus.value[key] === 'active') {
        agentStatus.value[key] = 'done'
      }
    })
  }

  // ── Message management ────────────────────────────────────────────
  function addMessage(message: ChatMessageItem) {
    messages.value.push(message)
    attachTracesToLastAssistant()
  }

  function createAssistantMessage(messageId?: string) {
    const now = Date.now()
    const message: ChatMessageItem = {
      id: messageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(now),
      status: 'thinking',
      reasoning: {
        status: 'thinking',
        title: '思考中...',
        expanded: true,
        startedAt: now,
        steps: [],
      },
      answer: {
        status: 'idle',
        content: '',
      },
    }
    messages.value.push(message)
    attachTracesToLastAssistant()
    return message
  }

  function getLastAssistantMessage() {
    for (let idx = messages.value.length - 1; idx >= 0; idx -= 1) {
      const message = messages.value[idx]
      if (message.role === 'assistant') return message
    }
    return null
  }

  function ensureAssistantMessage(messageId?: string) {
    const last = getLastAssistantMessage()
    if (last) {
      if (messageId && !last.id) last.id = messageId
      if (!last.reasoning) {
        last.reasoning = {
          status: last.status ?? 'thinking',
          title: '思考中...',
          expanded: true,
          startedAt: Date.now(),
          steps: [],
        }
      }
      if (!last.answer) {
        last.answer = {
          status: last.content ? 'done' : 'idle',
          content: last.content,
        }
      }
      return last
    }
    return createAssistantMessage(messageId)
  }

  function updateAssistantStatus(status: AgentMessageStatus) {
    const message = ensureAssistantMessage()
    message.status = status
    if (message.reasoning) {
      message.reasoning.status = status
      if (status === 'thinking') message.reasoning.title = '思考中...'
      if (status === 'tool_running') message.reasoning.title = '正在调用工具...'
      if (status === 'answering') message.reasoning.title = '正在生成最终回答...'
      if (status === 'error') message.reasoning.title = '分析过程遇到问题'
      if (status === 'done') {
        const endedAt = Date.now()
        message.reasoning.endedAt = message.reasoning.endedAt ?? endedAt
        message.reasoning.elapsedMs = message.reasoning.elapsedMs ?? (message.reasoning.endedAt - message.reasoning.startedAt)
        message.reasoning.title = `已思考（用时 ${formatElapsedSeconds(message.reasoning.elapsedMs)} 秒）`
      }
    }
  }

  function addReasoningStep(step: ReasoningStep) {
    const message = ensureAssistantMessage()
    const reasoning = message.reasoning!
    const idx = reasoning.steps.findIndex(item => item.id === step.id)
    if (idx >= 0) {
      reasoning.steps[idx] = { ...reasoning.steps[idx], ...step }
    } else {
      reasoning.steps.push(step)
    }
  }

  function updateReasoningStep(stepId: string, patch: Partial<ReasoningStep>) {
    const message = ensureAssistantMessage()
    const reasoning = message.reasoning!
    const step = reasoning.steps.find(item => item.id === stepId)
    if (step) Object.assign(step, patch)
  }

  function appendReasoningContent(stepId: string, delta: string) {
    if (!delta) return
    const message = ensureAssistantMessage()
    const step = message.reasoning?.steps.find(item => item.id === stepId)
    if (step) step.content += delta
  }

  function startAnswer() {
    const message = ensureAssistantMessage()
    message.status = 'answering'
    if (message.reasoning) {
      message.reasoning.status = 'answering'
      message.reasoning.title = '正在生成最终回答...'
    }
    message.answer = {
      status: 'answering',
      content: message.answer?.content ?? message.content ?? '',
      startedAt: message.answer?.startedAt ?? Date.now(),
    }
  }

  function appendAnswerContent(delta: string) {
    if (!delta) return
    const message = ensureAssistantMessage()
    if (!message.answer) startAnswer()
    message.answer!.content += delta
    message.content = message.answer!.content
  }

  function finishAnswer() {
    const message = ensureAssistantMessage()
    const endedAt = Date.now()
    if (!message.answer) {
      message.answer = {
        status: 'done',
        content: message.content,
      }
    }
    message.answer.status = 'done'
    message.answer.endedAt = endedAt
    message.content = message.answer.content
    message.status = 'done'
    if (message.reasoning) {
      message.reasoning.status = 'done'
      message.reasoning.endedAt = message.reasoning.endedAt ?? endedAt
      message.reasoning.elapsedMs = message.reasoning.elapsedMs ?? (message.reasoning.endedAt - message.reasoning.startedAt)
      message.reasoning.title = `已思考（用时 ${formatElapsedSeconds(message.reasoning.elapsedMs)} 秒）`
    }
  }

  function failAssistant(messageText: string, recoverable = true) {
    const message = ensureAssistantMessage()
    message.error = messageText
    if (!recoverable) {
      message.status = 'error'
      if (message.answer) {
        message.answer.status = 'error'
        message.answer.error = messageText
      }
    }
    if (message.reasoning) {
      message.reasoning.status = recoverable ? message.status ?? 'thinking' : 'error'
      if (!recoverable) message.reasoning.title = '分析过程遇到问题'
    }
  }

  // ── Execution trace management ─────────────────────────────────
  function addTrace(trace: ExecutionTrace) {
    pendingTraces.value.push(trace)
    attachTracesToLastAssistant()
  }

  function attachTracesToLastAssistant() {
    if (!pendingTraces.value.length) return

    for (let idx = messages.value.length - 1; idx >= 0; idx -= 1) {
      const last = messages.value[idx]
      if (last.role === 'assistant') {
        last.traces = [...pendingTraces.value]
        return
      }
    }
  }

  function resetTraces() {
    pendingTraces.value = []
  }

  function updateLastAssistantMessage(content: string) {
    const lastIdx = messages.value.length - 1
    if (lastIdx >= 0 && messages.value[lastIdx].role === 'assistant') {
      messages.value[lastIdx].content = content
    }
  }

  function removeThinkingMessage() {
    const idx = messages.value.findIndex(m => m.role === 'thinking')
    if (idx >= 0) {
      messages.value.splice(idx, 1)
    }
  }

  // ── Session operations (delegating to API) ────────────────────────
  async function deleteSession(sessionId: string) {
    try {
      await apiDeleteConversation(sessionId)
      sessions.value = sessions.value.filter(s => s.session_id !== sessionId)

      // If we deleted the current session, clear it
      if (currentSessionId.value === sessionId) {
        clearCurrentSession()
      }
      return true
    } catch (e) {
      console.error('[AI Store] Failed to delete session:', e)
      return false
    }
  }

  async function renameSession(sessionId: string, title: string) {
    try {
      await apiRenameConversation(sessionId, title)
      const session = sessions.value.find(s => s.session_id === sessionId)
      if (session) {
        session.title = title
      }
      if (currentSessionId.value === sessionId) {
        sessionTitle.value = title
      }
      return true
    } catch (e) {
      console.error('[AI Store] Failed to rename session:', e)
      return false
    }
  }

  // ── Input draft management ────────────────────────────────────────
  function setInputDraft(draft: string) {
    inputDraft.value = draft
    persistToLocalStorage()
  }

  function toggleDrawer() {
    drawerOpen.value = !drawerOpen.value
    persistToLocalStorage()
  }

  function setDrawerOpen(open: boolean) {
    drawerOpen.value = open
    persistToLocalStorage()
  }

  return {
    // State
    sessions,
    sessionsLoading,
    currentSessionId,
    messages,
    snapshot,
    sessionTitle,
    isLoadingSession,
    inputDraft,
    drawerOpen,
    agentStatus,
    pendingTraces,

    // Computed
    riskLevel,
    queryCount,
    planInfo,
    isNewSession,

    // Actions
    initFromLocalStorage,
    persistToLocalStorage,
    fetchSessions,
    loadSession,
    startNewSession,
    clearCurrentSession,
    setSessionId,
    updateSnapshot,
    resetAgentStatus,
    setAgentStatus,
    finalizeAgentStatuses,
    addMessage,
    updateLastAssistantMessage,
    createAssistantMessage,
    ensureAssistantMessage,
    updateAssistantStatus,
    addReasoningStep,
    updateReasoningStep,
    appendReasoningContent,
    startAnswer,
    appendAnswerContent,
    finishAnswer,
    failAssistant,
    removeThinkingMessage,
    addTrace,
    attachTracesToLastAssistant,
    resetTraces,
    deleteSession,
    renameSession,
    setInputDraft,
    toggleDrawer,
    setDrawerOpen,
  }
})

function formatElapsedSeconds(ms: number) {
  return Math.max(1, Math.ceil(ms / 1000))
}
