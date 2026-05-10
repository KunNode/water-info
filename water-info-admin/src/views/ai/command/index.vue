<template>
  <div class="fm-ai-page">
    <div class="fm-ai-topbar">
      <div class="fm-ai-topbar__brand">
        <span class="tb-dot" />
        <span class="tb-title">AI 指挥台</span>
        <span class="fm-ai-live" :class="{ active: loading }">
          <span class="fm-dot" :class="loading ? 'warn' : 'ok'" />
          {{ loading ? '分析中' : '待命' }}
        </span>
        <span class="tb-sub">翠屏湖 · 研判席</span>
      </div>

      <span class="fm-ai-topbar__sep" />

      <div class="fm-ai-topbar__session">
        <span class="ses-label">SESSION</span>
        <strong class="ses-id">{{ sessionShort }}</strong>
      </div>

      <span class="fm-ai-topbar__sep" />

      <div class="fm-ai-topbar__metrics">
        <div class="tb-metric">
          <span>交互轮次</span>
          <strong>{{ store.queryCount }}</strong>
        </div>
        <div class="tb-metric">
          <span>执行步骤</span>
          <strong>{{ traceCount }}{{ activeTraceCount ? ` · ${activeTraceCount}↑` : '' }}</strong>
        </div>
        <div class="tb-metric">
          <span>风险态势</span>
          <strong :class="riskToneClass">{{ riskLabel }}</strong>
        </div>
        <div class="tb-metric">
          <span>预案进度</span>
          <strong>{{ planProgressLabel }}</strong>
        </div>
        <div class="tb-metric">
          <span>会话时间</span>
          <strong>{{ startTime || '--:--:--' }}</strong>
        </div>
      </div>

      <div class="fm-ai-topbar__actions">
        <el-button size="small" class="fm-ai-head-btn" @click="handleNewSession">
          <el-icon><Plus /></el-icon>新会话
        </el-button>
        <el-button size="small" class="fm-ai-head-btn" @click="toggleDrawer">
          <el-icon><ChatLineRound /></el-icon>会话记录
        </el-button>
        <el-button size="small" type="primary" plain @click="goBack">
          <el-icon><Back /></el-icon>返回
        </el-button>
      </div>
    </div>

    <div class="fm-ai-grid">
      <ChatPanel
        ref="chatPanelRef"
        :messages="store.messages"
        :loading="loading"
        class="fm-ai-grid__chat"
        @send="sendQuery"
      />

      <div class="fm-ai-grid__side">
        <RiskPanel />
        <PlanStatus :planInfo="store.planInfo" />
        <ActiveAlerts />
        <SessionInfo
          :sessionId="store.currentSessionId"
          :startTime="startTime"
          :queryCount="store.queryCount"
        />
      </div>
    </div>

    <SessionDrawer
      ref="sessionDrawerRef"
      v-model="store.drawerOpen"
      :currentSessionId="store.currentSessionId"
      @select="handleSessionSelect"
      @new="handleNewSession"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Back, Plus, ChatLineRound } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAgentStream } from '@/composables/useAgentStream'
import { getStreamUrl } from '@/api/flood'
import { useAiConversationStore } from '@/stores/aiConversation'
import { useSituationStore } from '@/stores/situation'
import type { AgentStreamEvent, ReasoningStep, ReasoningStepStatus } from '@/types/agentStream'
import { mapToolCallTitle, redactSensitive, summarizeToolResult } from '@/utils/agentToolCopy'

// Sub-components
import ChatPanel from './components/ChatPanel.vue'
import RiskPanel from './components/RiskPanel.vue'
import PlanStatus from './components/PlanStatus.vue'
import ActiveAlerts from './components/ActiveAlerts.vue'
import SessionInfo from './components/SessionInfo.vue'
import SessionDrawer from './components/SessionDrawer.vue'

const router = useRouter()
const route = useRoute()
const store = useAiConversationStore()
const situationStore = useSituationStore()
const { loading, error, start, stop, reset, onEvent, onText } = useAgentStream()

// ── Session drawer ──────────────────────────────────────────────
const sessionDrawerRef = ref<InstanceType<typeof SessionDrawer> | null>(null)
const chatPanelRef = ref<InstanceType<typeof ChatPanel> | null>(null)
const startTime = ref('')

function scrollChatToBottom() {
  chatPanelRef.value?.scrollToBottom()
}

async function handleSessionSelect(newSessionId: string) {
  if (!newSessionId || newSessionId === store.currentSessionId) return

  try {
    await store.loadSession(newSessionId)
    startTime.value = new Date().toLocaleTimeString()
    resetStreamBuffers()
    reset()
    store.setDrawerOpen(false)
    syncRouteSession(newSessionId)
    await nextTick()
    scrollChatToBottom()
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    ElMessage.error(msg || '加载会话失败，请稍后重试')
  }
}

function handleNewSession() {
  store.startNewSession()
  startTime.value = ''
  resetStreamBuffers()
  reset()

  router.replace({ name: 'AICommand', query: {} })
}

function toggleDrawer() {
  store.drawerOpen = !store.drawerOpen
}

// ── Stream buffers: RAF-batched reasoning, typewriter answer ─────
const activeToolNames = new Map<string, string>()
const reasoningBuffers = new Map<string, string>()
const legacyAgentStepIds = new Map<string, string>()
let reasoningRaf = 0
let answerRaf = 0
let answerBuffer = ''
let finishAnswerWhenBufferEmpty = false
let lastLegacyFinal = ''
const ANSWER_CHARS_PER_FRAME = 5

// ── Risk state ────────────────────────────────────────
const riskMap: Record<string, { label: string; tag: string }> = {
  none:     { label: '正常',     tag: '' },
  low:      { label: '低风险',   tag: 'fm-tag--info' },
  moderate: { label: '中等风险', tag: 'fm-tag--warn' },
  high:     { label: '高风险',   tag: 'fm-tag--danger' },
  critical: { label: '极高风险', tag: 'fm-tag--danger' },
}
const riskLabel = computed(() => riskMap[store.riskLevel]?.label ?? '正常')
const riskTagClass = computed(() => riskMap[store.riskLevel]?.tag ?? '')
const riskToneClass = computed(() => (store.riskLevel === 'none' ? 'tone-ok' : riskTagClass.value.replace('fm-tag--', 'tone-')))
const sessionShort = computed(() => store.currentSessionId ? store.currentSessionId.slice(0, 8).toUpperCase() : 'DRAFT')
const traceCount = computed(() => store.pendingTraces.length + currentReasoningSteps.value.length)
const activeTraceCount = computed(() =>
  store.pendingTraces.filter((trace) => trace.status === 'started' || trace.status === 'active' || trace.status === 'running').length +
  currentReasoningSteps.value.filter((step) => step.status === 'running' || step.status === 'pending').length,
)
const currentReasoningSteps = computed(() => store.messages.flatMap((message) => message.reasoning?.steps ?? []))
const planProgressLabel = computed(() => {
  const plan = store.planInfo
  if (!plan) return '待生成'
  if (!plan.total) return plan.status || '运行中'
  return `${Math.round((plan.completed / plan.total) * 100)}%`
})

function resetStreamBuffers() {
  if (reasoningRaf) cancelAnimationFrame(reasoningRaf)
  if (answerRaf) cancelAnimationFrame(answerRaf)
  reasoningRaf = 0
  answerRaf = 0
  answerBuffer = ''
  finishAnswerWhenBufferEmpty = false
  lastLegacyFinal = ''
  activeToolNames.clear()
  reasoningBuffers.clear()
  legacyAgentStepIds.clear()
}

function appendReasoningDelta(stepId: string, delta: string) {
  if (!delta) return
  reasoningBuffers.set(stepId, `${reasoningBuffers.get(stepId) ?? ''}${delta}`)
  if (!reasoningRaf) reasoningRaf = requestAnimationFrame(flushReasoningBuffers)
}

function flushReasoningBuffers() {
  reasoningRaf = 0
  for (const [stepId, delta] of reasoningBuffers.entries()) {
    store.appendReasoningContent(stepId, delta)
  }
  reasoningBuffers.clear()
}

function appendAnswerDelta(delta: string) {
  if (!delta) return
  store.startAnswer()
  answerBuffer += delta
  if (!answerRaf) answerRaf = requestAnimationFrame(flushAnswerBuffer)
}

function flushAnswerBuffer() {
  answerRaf = 0
  const chunk = answerBuffer.slice(0, ANSWER_CHARS_PER_FRAME)
  answerBuffer = answerBuffer.slice(ANSWER_CHARS_PER_FRAME)
  if (chunk) store.appendAnswerContent(chunk)

  if (answerBuffer) {
    answerRaf = requestAnimationFrame(flushAnswerBuffer)
    return
  }

  if (finishAnswerWhenBufferEmpty) {
    finishAnswerWhenBufferEmpty = false
    store.finishAnswer()
  }
}

function finishAnswerAfterTypewriter() {
  if (answerBuffer) {
    finishAnswerWhenBufferEmpty = true
    if (!answerRaf) answerRaf = requestAnimationFrame(flushAnswerBuffer)
  } else {
    store.finishAnswer()
  }
}

function formatEvidenceUpdate(items: Array<{
  citation_id: string
  content: string
  document_title: string
  source_uri?: string
  heading_path?: string[]
}>) {
  if (!items.length) return ''
  return [
    '## 命中证据',
    ...items.map((item) => {
      const heading = item.heading_path?.length ? item.heading_path.join(' / ') : '正文'
      const source = item.source_uri ? ` - ${item.source_uri}` : ''
      return `- ${item.citation_id} **${item.document_title}** / ${heading}${source}\n  ${item.content.slice(0, 180)}`
    }),
  ].join('\n')
}

// ── SSE structured events ────────────────────────────────────────
onMounted(async () => {
  store.initFromLocalStorage()
  await store.fetchSessions()

  const sessionIdFromRoute = typeof route.query.sessionId === 'string'
    ? route.query.sessionId
    : undefined
  if (sessionIdFromRoute) {
    await store.loadSession(sessionIdFromRoute)
    startTime.value = new Date().toLocaleTimeString()
  } else if (store.currentSessionId) {
    await store.loadSession(store.currentSessionId)
    startTime.value = new Date().toLocaleTimeString()
    syncRouteSession(store.currentSessionId)
  }

  situationStore.connectAssessmentStream()

  onEvent(handleStreamEvent)
  onText(appendAnswerDelta)

  void situationStore.ensureFresh()
})

watch(loading, (isLoading) => {
  if (isLoading) {
    const hasActive = Object.values(store.agentStatus).some((s) => s === 'active' || s === 'done')
    if (!hasActive) store.setAgentStatus('supervisor', 'active')
  } else {
    if (reasoningRaf) flushReasoningBuffers()
    if (answerBuffer || store.ensureAssistantMessage().answer?.status === 'answering') finishAnswerAfterTypewriter()
    store.finalizeAgentStatuses()
    store.attachTracesToLastAssistant()
  }
})

function handleStreamEvent(event: AgentStreamEvent) {
  switch (event.type) {
    case 'session_init':
      bindSession(event.sessionId)
      break
    case 'message_start':
      store.ensureAssistantMessage(event.messageId)
      if (event.sessionId) bindSession(event.sessionId)
      break
    case 'thought_start':
      startThoughtStep(event.id ?? event.thoughtId ?? createId('thought'), event.title ?? '正在分析问题', event.content)
      break
    case 'thought_delta':
      appendReasoningDelta(event.id ?? event.thoughtId ?? getFallbackStepId('thought'), event.delta)
      break
    case 'thought_end':
      finishReasoningStep(event.id ?? event.thoughtId ?? getFallbackStepId('thought'), 'success', event.durationMs)
      break
    case 'tool_start':
      startToolStep(event)
      break
    case 'tool_delta':
      appendReasoningDelta(event.id ?? event.toolCallId ?? getFallbackStepId('tool'), event.delta)
      break
    case 'tool_result':
      applyToolResult(event.id ?? event.toolCallId ?? getFallbackStepId('tool'), event)
      break
    case 'tool_end':
      finishToolStep(event.id ?? event.toolCallId ?? getFallbackStepId('tool'), event.status === 'error' ? 'error' : 'success', event.durationMs, event.error)
      break
    case 'answer_start':
      store.startAnswer()
      break
    case 'answer_delta':
      appendAnswerDelta(event.delta)
      break
    case 'answer_end':
      finishAnswerAfterTypewriter()
      break
    case 'error':
      // Backend emits `{ type, message, code?, recoverable? }` per design §5 and
      // Task 3.3. Treat missing `recoverable` as recoverable=true (soft
      // degradation) and pass `code` through for observability.
      handleRecoverableError(event.message, event.recoverable !== false, event.code)
      break
    case 'agent_update':
      store.setAgentStatus(event.agent, event.status)
      break
    case 'risk_update':
      store.updateSnapshot({ risk_level: event.level })
      break
    case 'plan_update':
      store.updateSnapshot({
        plan_info: {
          plan_name: event.name,
          status: event.status,
          actions_count: event.total,
        },
      })
      break
    case 'evidence_update':
      if (event.items?.length) upsertLegacyStep(event.agent, '命中知识库证据', formatEvidenceUpdate(event.items), 'success')
      break
    case 'agent_message':
      handleLegacyAgentMessage(event.agent, event.content)
      break
    case 'trace_update':
      handleLegacyTrace(event)
      break
  }
}

function bindSession(sessionId: string) {
  if (!store.currentSessionId) {
    store.setSessionId(sessionId)
    startTime.value = new Date().toLocaleTimeString()
  }
  syncRouteSession(store.currentSessionId || sessionId)
}

function syncRouteSession(sessionId: string) {
  if (!sessionId || route.query.sessionId === sessionId) return
  router.replace({ name: 'AICommand', query: { ...route.query, sessionId } })
}

function startThoughtStep(stepId: string, title: string, content = '') {
  store.updateAssistantStatus('thinking')
  addStep({
    id: stepId,
    kind: 'thought',
    title,
    content,
    status: 'running',
    startedAt: Date.now(),
  })
}

function startToolStep(event: Extract<AgentStreamEvent, { type: 'tool_start' }>) {
  const stepId = event.id ?? event.toolCallId ?? createId('tool')
  const title = event.displayName || mapToolCallTitle(event.toolName)
  activeToolNames.set(stepId, event.toolName)
  store.updateAssistantStatus('tool_running')
  addStep({
    id: stepId,
    kind: 'tool',
    title,
    content: event.inputSummary ?? summarizeSafeInput(event.arguments),
    status: 'running',
    startedAt: Date.now(),
    tool: {
      name: event.toolName,
      displayName: title,
      inputSummary: event.inputSummary,
    },
  })
}

function applyToolResult(stepId: string, event: Extract<AgentStreamEvent, { type: 'tool_result' }>) {
  const toolName = activeToolNames.get(stepId)
  const resultSummary = event.error
    ? mapToolCallTitle(toolName, 'fallback')
    : summarizeToolResult(toolName, event.data, event.summary)

  store.updateReasoningStep(stepId, {
    status: event.error ? 'error' : 'running',
    title: event.error ? mapToolCallTitle(toolName, 'fallback') : mapToolCallTitle(toolName, 'success'),
    tool: {
      name: toolName ?? 'unknown',
      displayName: mapToolCallTitle(toolName, event.error ? 'fallback' : 'success'),
      resultSummary,
    },
  })
}

function finishToolStep(stepId: string, status: ReasoningStepStatus, durationMs?: number, errorText?: string) {
  const toolName = activeToolNames.get(stepId)
  store.updateReasoningStep(stepId, {
    status,
    title: status === 'error' ? mapToolCallTitle(toolName, 'fallback') : mapToolCallTitle(toolName, 'success'),
    endedAt: Date.now(),
    durationMs,
  })
  if (status === 'error' && errorText) handleRecoverableError(errorText, true)
}

function finishReasoningStep(stepId: string, status: ReasoningStepStatus, durationMs?: number) {
  store.updateReasoningStep(stepId, {
    status,
    endedAt: Date.now(),
    durationMs,
  })
}

function handleRecoverableError(message: string, recoverable: boolean, code?: string) {
  // Unrecoverable errors (e.g. backend `memory_load_failed` from Task 3.3):
  // terminate the stream, surface a top-level toast so the user isn't left
  // guessing, and mark the assistant message as failed. Recoverable errors
  // keep the existing degraded flow (reasoning step + retry hint only).
  if (!recoverable) {
    stop()
    store.failAssistant(message, false)
    ElMessage.error(message || '会话流已终止，请稍后重试')
  } else {
    store.failAssistant(message, true)
  }
  addStep({
    id: createId('error'),
    kind: 'thought',
    title: recoverable ? '执行过程已降级' : '执行过程失败',
    content: recoverable
      ? `${message}，正在尝试继续生成最终回答。`
      : code
        ? `${message}（错误码：${code}）`
        : message,
    status: 'error',
    startedAt: Date.now(),
    endedAt: Date.now(),
  })
}

function handleLegacyAgentMessage(agent: string, content: string) {
  if (agent === 'final_response') {
    const delta = content.startsWith(lastLegacyFinal) ? content.slice(lastLegacyFinal.length) : content
    lastLegacyFinal = content
    appendAnswerDelta(delta)
    return
  }

  upsertLegacyStep(agent, legacyAgentTitle(agent), content, 'running')
}

function handleLegacyTrace(event: Extract<AgentStreamEvent, { type: 'trace_update' }>) {
  const status = normalizeTraceStatus(event.status)
  const stepId = `trace-${event.phase}-${event.tool_name ?? event.title}`
  const isTool = Boolean(event.tool_name) || event.phase === 'tool_call'
  const title = event.tool_name
    ? mapToolCallTitle(event.tool_name, status === 'error' ? 'fallback' : status === 'success' ? 'success' : 'running')
    : event.title

  if (isTool && event.tool_name) activeToolNames.set(stepId, event.tool_name)
  addStep({
    id: stepId,
    kind: isTool ? 'tool' : 'thought',
    title,
    content: event.detail ?? '',
    status,
    startedAt: Date.now(),
    endedAt: status === 'success' || status === 'error' ? Date.now() : undefined,
    durationMs: typeof event.metadata?.duration_ms === 'number' ? event.metadata.duration_ms : undefined,
    tool: event.tool_name ? {
      name: event.tool_name,
      displayName: title,
      inputSummary: typeof event.metadata?.input_summary === 'string' ? event.metadata.input_summary : undefined,
      resultSummary: typeof event.metadata?.output_summary === 'string' ? event.metadata.output_summary : undefined,
    } : undefined,
  })
}

function upsertLegacyStep(agent: string, title: string, content: string, status: ReasoningStepStatus) {
  const stepId = legacyAgentStepIds.get(agent) ?? `legacy-${agent}`
  legacyAgentStepIds.set(agent, stepId)
  addStep({
    id: stepId,
    kind: 'thought',
    title,
    content,
    status,
    startedAt: Date.now(),
    endedAt: status === 'success' || status === 'error' ? Date.now() : undefined,
  })
}

function addStep(step: ReasoningStep) {
  store.addReasoningStep(step)
}

function summarizeSafeInput(input?: Record<string, unknown>) {
  if (!input) return ''
  const safe = redactSensitive(input)
  const keys = Object.keys(safe as Record<string, unknown>).slice(0, 3)
  return keys.length ? `已接收 ${keys.join('、')} 等查询条件` : ''
}

function legacyAgentTitle(agent: string) {
  const map: Record<string, string> = {
    supervisor: '正在识别任务意图',
    data_analyst: '正在汇总水雨情数据',
    risk_assessor: '正在评估风险等级',
    plan_generator: '正在生成处置方案',
    knowledge_retriever: '正在检索知识库',
    resource_dispatcher: '正在匹配资源',
    notification: '正在整理通知方案',
  }
  return map[agent] ?? '正在分析...'
}

function normalizeTraceStatus(status: string): ReasoningStepStatus {
  if (status === 'failed' || status === 'error') return 'error'
  if (status === 'done' || status === 'success' || status === 'completed') return 'success'
  if (status === 'pending') return 'pending'
  return 'running'
}

function getFallbackStepId(prefix: string) {
  return `${prefix}-active`
}

function createId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

async function sendQuery(queryText: string) {
  if (!queryText.trim() || loading.value) return

  store.resetAgentStatus()
  store.resetTraces()
  resetStreamBuffers()

  store.addMessage({ role: 'user', content: queryText, timestamp: new Date() })
  store.createAssistantMessage()
  reset()

  try {
    const payload: { message: string; sessionId?: string; stream: boolean } = {
      message: queryText,
      stream: true,
    }
    if (store.currentSessionId) payload.sessionId = store.currentSessionId
    await start(getStreamUrl(), payload)
    await store.fetchSessions()
    sessionDrawerRef.value?.refresh()
    if (error.value) ElMessage.error(error.value)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    ElMessage.error(error.value || msg || '请求失败')
    store.failAssistant(error.value || msg || '请求失败', false)
  }
}

function goBack() {
  stop()
  router.push('/dashboard')
}
</script>

<style lang="scss">
/* Only when AI command page is active, reduce layout bottom padding */
.fm-main__body:has(.fm-ai-page) {
  padding-bottom: 16px;
}
</style>

<style scoped lang="scss">
.fm-ai-page {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: calc(100vh - var(--fm-topbar-h) - var(--fm-tags-h) - 38px);
  overflow: hidden;
  position: relative;
}

// ── Single-row command topbar ─────────────────────────────────────────
.fm-ai-topbar {
  display: flex;
  align-items: stretch;
  height: 48px;
  flex-shrink: 0;
  border: 1px solid var(--fm-line);
  border-radius: var(--fm-radius);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.025), transparent 44%),
    var(--fm-grad-panel);
  box-shadow: var(--fm-shadow-card);
  overflow: hidden;

  &__sep {
    width: 1px;
    background: var(--fm-line);
    flex-shrink: 0;
    align-self: stretch;
  }

  &__brand {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 16px;
    flex-shrink: 0;

    .tb-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--fm-brand-2);
      box-shadow: 0 0 8px var(--fm-brand-2);
      flex-shrink: 0;
    }

    .tb-title {
      font-size: 16px;
      font-weight: 650;
      color: var(--fm-fg);
      white-space: nowrap;
      letter-spacing: 0;
    }

    .tb-sub {
      font-size: 10px;
      color: var(--fm-fg-mute);
      white-space: nowrap;
      font-family: var(--fm-font-mono);
      letter-spacing: 0.04em;
    }
  }

  &__session {
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 0 14px;
    gap: 2px;
    flex-shrink: 0;

    .ses-label {
      font-family: var(--fm-font-mono);
      font-size: 9px;
      color: var(--fm-fg-mute);
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }

    .ses-id {
      font-family: var(--fm-font-mono);
      font-size: 13px;
      color: var(--fm-fg);
      font-weight: 650;
      letter-spacing: 0;
    }
  }

  &__metrics {
    display: flex;
    flex: 1;
    align-items: stretch;
    min-width: 0;
  }

  &__actions {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 12px;
    border-left: 1px solid var(--fm-line);
    flex-shrink: 0;
  }
}

.tb-metric {
  display: flex;
  flex-direction: column;
  justify-content: center;
  flex: 1;
  padding: 0 12px;
  border-left: 1px solid var(--fm-line);
  gap: 2px;
  min-width: 0;

  span {
    font-family: var(--fm-font-mono);
    font-size: 9px;
    color: var(--fm-fg-mute);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    white-space: nowrap;
  }

  strong {
    font-size: 13px;
    font-weight: 650;
    color: var(--fm-fg);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.fm-ai-live {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border: 1px solid rgba(43, 217, 159, 0.32);
  border-radius: 999px;
  color: #4de2b3;
  background: rgba(43, 217, 159, 0.1);
  font-family: var(--fm-font-mono);
  font-size: 10px;
  letter-spacing: 0.04em;
  white-space: nowrap;

  &.active {
    color: #ffc96e;
    border-color: rgba(255, 181, 71, 0.34);
    background: rgba(255, 181, 71, 0.1);
  }
}

.tone-ok,
.tone-info {
  color: var(--fm-ok) !important;
}

.tone-warn {
  color: var(--fm-warn) !important;
}

.tone-danger {
  color: var(--fm-danger) !important;
}

.fm-ai-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(256px, 296px);
  grid-template-rows: 1fr;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow: hidden;

  &__chat {
    grid-column: 1;
    min-height: 0;
  }

  &__side {
    grid-column: 2;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 0;
    min-height: 0;
    overflow-y: auto;
    padding-right: 4px;

    &::-webkit-scrollbar {
      width: 4px;
    }
    &::-webkit-scrollbar-track {
      background: transparent;
    }
    &::-webkit-scrollbar-thumb {
      background: var(--fm-line-2);
      border-radius: 2px;
    }

    :deep(.fm-card__head) {
      padding: 8px 14px;
    }

    :deep(.fm-card__body) {
      padding: 10px 14px;
    }
  }
}

@media (max-width: 1100px) {
  .fm-ai-grid {
    grid-template-columns: 1fr;
    grid-template-rows: 560px auto;

    &__chat {
      grid-column: 1;
    }
    &__side {
      grid-column: 1;
      overflow-y: visible;
      max-height: none;
    }
  }
}

.fm-ai-head-btn {
  :deep(.el-icon) {
    margin-right: 3px;
  }
}

@media (max-width: 1100px) {
  .fm-ai-topbar__session,
  .fm-ai-topbar__sep:first-of-type {
    display: none;
  }

  .tb-metric:nth-child(n + 4) {
    display: none;
  }
}

@media (max-width: 760px) {
  .fm-ai-page {
    height: auto;
    overflow: visible;
  }

  .fm-ai-topbar {
    overflow-x: auto;
    overflow-y: hidden;
  }
}
</style>
