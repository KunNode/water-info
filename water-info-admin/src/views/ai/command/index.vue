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
          <span>智能体</span>
          <strong>{{ doneAgentCount }}/{{ totalAgentCount }}{{ activeAgentCount ? ` · ${activeAgentCount}↑` : '' }}</strong>
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
        :messages="store.messages"
        :loading="loading"
        class="fm-ai-grid__chat"
        @send="sendQuery"
      />

      <div class="fm-ai-grid__side">
        <AgentTimeline :agentStatus="store.agentStatus" />
        <RiskPanel :riskLevel="store.riskLevel" />
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
import { useSSE } from '@/composables/useSSE'
import type { SSEEventType } from '@/composables/useSSE'
import { getStreamUrl } from '@/api/flood'
import { useAiConversationStore } from '@/stores/aiConversation'

// Sub-components
import ChatPanel from './components/ChatPanel.vue'
import AgentTimeline from './components/AgentTimeline.vue'
import RiskPanel from './components/RiskPanel.vue'
import PlanStatus from './components/PlanStatus.vue'
import ActiveAlerts from './components/ActiveAlerts.vue'
import SessionInfo from './components/SessionInfo.vue'
import SessionDrawer from './components/SessionDrawer.vue'

const router = useRouter()
const route = useRoute()
const store = useAiConversationStore()
const { fullText, loading, error, start, stop, reset, onStructuredEvent } = useSSE()

// True once the current query receives at least one agent_message structured event.
const hasAgentMessages = ref(false)

// ── Session drawer ──────────────────────────────────────────────
const sessionDrawerRef = ref<InstanceType<typeof SessionDrawer> | null>(null)
const startTime = ref('')

async function handleSessionSelect(newSessionId: string) {
  if (!newSessionId || newSessionId === store.currentSessionId) return

  await store.loadSession(newSessionId)
  startTime.value = new Date().toLocaleTimeString()

  typewriterQueue.value = []
  isTyping.value = false
  currentQueryBubbleIdx.clear()
  agentLatestContent.clear()
  reset()

  router.replace({ name: 'AICommandSession', params: { sessionId: newSessionId } })
}

function handleNewSession() {
  store.startNewSession()
  startTime.value = ''
  typewriterQueue.value = []
  isTyping.value = false
  currentQueryBubbleIdx.clear()
  agentLatestContent.clear()
  reset()

  router.replace({ name: 'AICommand' })
}

function toggleDrawer() {
  store.drawerOpen = !store.drawerOpen
}

// ── Typewriter queue ─────────────────────────────────────────────
interface TypewriterTask {
  agent: string
  fullContent: string
}

const typewriterQueue = ref<TypewriterTask[]>([])
const isTyping = ref(false)
const CHARS_PER_TICK = 4
const TICK_MS = 16

const currentQueryBubbleIdx = new Map<string, number>()
const agentLatestContent = new Map<string, string>()

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
const sessionModeLabel = computed(() => store.currentSessionId ? '已接管历史会话' : '草稿会话')
const totalAgentCount = computed(() => Object.keys(store.agentStatus).length)
const doneAgentCount = computed(() =>
  Object.values(store.agentStatus).filter((status) => status === 'done').length,
)
const activeAgentCount = computed(() =>
  Object.values(store.agentStatus).filter((status) => status === 'active').length,
)
const planProgressLabel = computed(() => {
  const plan = store.planInfo
  if (!plan) return '待生成'
  if (!plan.total) return plan.status || '运行中'
  return `${Math.round((plan.completed / plan.total) * 100)}%`
})

// ── Message helpers ─────────────────────────────────────────────
function removeThinkingBubble() {
  const idx = store.messages.findIndex((m) => m.role === 'thinking')
  if (idx >= 0) {
    store.messages.splice(idx, 1)
    for (const [k, v] of currentQueryBubbleIdx.entries()) {
      if (v > idx) currentQueryBubbleIdx.set(k, v - 1)
    }
  }
}

function enqueueAgentMessage(agent: string, content: string) {
  removeThinkingBubble()
  agentLatestContent.set(agent, content)

  const existingIdx = currentQueryBubbleIdx.get(agent) ?? -1
  if (existingIdx >= 0) {
    const existing = store.messages[existingIdx]
    if (existing.agentStatus === 'typing') return
    existing.content = content
    return
  }

  const idx = store.messages.length
  currentQueryBubbleIdx.set(agent, idx)
  store.addMessage({
    role: 'agent',
    content: '',
    timestamp: new Date(),
    agent,
    agentStatus: 'typing',
  })
  typewriterQueue.value.push({ agent, fullContent: content })
  if (!isTyping.value) processTypewriterQueue()
}

async function processTypewriterQueue() {
  if (typewriterQueue.value.length === 0) {
    isTyping.value = false
    return
  }
  isTyping.value = true
  const task = typewriterQueue.value.shift()!

  const actualIdx = currentQueryBubbleIdx.get(task.agent) ?? -1
  if (actualIdx < 0) {
    processTypewriterQueue()
    return
  }

  let pos = store.messages[actualIdx].content.length
  let full = agentLatestContent.get(task.agent) ?? task.fullContent
  while (pos < full.length) {
    pos = Math.min(pos + CHARS_PER_TICK, full.length)
    store.messages[actualIdx].content = full.slice(0, pos)
    await nextTick()
    await new Promise<void>((r) => setTimeout(r, TICK_MS))
    full = agentLatestContent.get(task.agent) ?? task.fullContent
  }

  store.messages[actualIdx].agentStatus = 'done'
  processTypewriterQueue()
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

  const sessionIdFromRoute = route.params.sessionId as string | undefined
  if (sessionIdFromRoute) {
    await store.loadSession(sessionIdFromRoute)
    startTime.value = new Date().toLocaleTimeString()
  } else if (store.currentSessionId) {
    await store.loadSession(store.currentSessionId)
    startTime.value = new Date().toLocaleTimeString()
  }

  onStructuredEvent((event: SSEEventType) => {
    if (event.type === 'session_init') {
      if (!store.currentSessionId) {
        store.setSessionId(event.sessionId)
        startTime.value = new Date().toLocaleTimeString()
        router.replace({ name: 'AICommandSession', params: { sessionId: event.sessionId } })
      }
    } else if (event.type === 'agent_update') {
      store.setAgentStatus(event.agent, event.status)
    } else if (event.type === 'risk_update') {
      store.updateSnapshot({ risk_level: event.level })
    } else if (event.type === 'plan_update') {
      store.updateSnapshot({
        plan_info: {
          plan_name: event.name,
          status: event.status,
          actions_count: event.total,
        },
      })
    } else if (event.type === 'evidence_update' && event.items?.length) {
      store.addMessage({
        role: 'agent',
        agent: event.agent,
        content: formatEvidenceUpdate(event.items),
        timestamp: new Date(),
        agentStatus: 'done',
      })
    } else if (event.type === 'agent_message') {
      hasAgentMessages.value = true
      enqueueAgentMessage(event.agent, event.content)
    }
  })
})

watch(fullText, (val) => {
  if (!val || hasAgentMessages.value) return
  removeThinkingBubble()
  const last = store.messages[store.messages.length - 1]
  if (last?.role === 'assistant') {
    last.content = val
  } else {
    store.addMessage({ role: 'assistant', content: val, timestamp: new Date() })
  }
})

watch(loading, (isLoading) => {
  if (isLoading) {
    const hasActive = Object.values(store.agentStatus).some((s) => s === 'active' || s === 'done')
    if (!hasActive) store.setAgentStatus('supervisor', 'active')
  } else {
    store.finalizeAgentStatuses()
  }
})

async function sendQuery(queryText: string) {
  if (!queryText.trim() || loading.value) return

  store.resetAgentStatus()

  hasAgentMessages.value = false
  typewriterQueue.value = []
  isTyping.value = false
  currentQueryBubbleIdx.clear()
  agentLatestContent.clear()

  store.addMessage({ role: 'user', content: queryText, timestamp: new Date() })
  store.addMessage({ role: 'thinking', content: '正在分析，请稍候…', timestamp: new Date() })
  reset()

  try {
    const payload: { query: string; sessionId?: string } = { query: queryText }
    if (store.currentSessionId) payload.sessionId = store.currentSessionId
    await start(getStreamUrl(), payload)
    await store.fetchSessions()
    sessionDrawerRef.value?.refresh()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    ElMessage.error(error.value || msg || '请求失败')
    removeThinkingBubble()
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
