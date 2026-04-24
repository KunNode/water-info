<template>
  <div class="fm-ai-page">
    <div class="fm-page-head">
      <h1>AI 命令中心</h1>
      <span class="sub">
        //
        <template v-if="store.currentSessionId">session · {{ store.currentSessionId.slice(0, 8) }}</template>
        <template v-else>session · draft</template>
        · {{ store.queryCount }} 次交互
      </span>
      <span class="sp" />

      <span v-if="store.riskLevel !== 'none'" class="fm-tag" :class="riskTagClass">
        <span class="fm-dot" :class="riskDotClass" />{{ riskLabel }}
      </span>

      <span class="fm-tag" :class="{ 'fm-tag--warn': loading, 'fm-tag--ok': !loading }">
        <span class="fm-dot" :class="loading ? 'warn' : 'ok'" />
        {{ loading ? '分析中' : '待命' }}
      </span>

      <el-button class="fm-ai-head-btn" @click="handleNewSession">
        <el-icon><Plus /></el-icon>新会话
      </el-button>
      <el-button class="fm-ai-head-btn" @click="toggleDrawer">
        <el-icon><ChatLineRound /></el-icon>会话记录
      </el-button>
      <el-button type="primary" plain @click="goBack">
        <el-icon><Back /></el-icon>返回
      </el-button>
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
const riskMap: Record<string, { label: string; tag: string; dot: string }> = {
  none:     { label: '正常',     tag: '',              dot: 'off' },
  low:      { label: '低风险',   tag: 'fm-tag--info',  dot: 'ok' },
  moderate: { label: '中等风险', tag: 'fm-tag--warn',  dot: 'warn' },
  high:     { label: '高风险',   tag: 'fm-tag--danger', dot: 'danger' },
  critical: { label: '极高风险', tag: 'fm-tag--danger', dot: 'danger' },
}
const riskLabel = computed(() => riskMap[store.riskLevel]?.label ?? '正常')
const riskTagClass = computed(() => riskMap[store.riskLevel]?.tag ?? '')
const riskDotClass = computed(() => riskMap[store.riskLevel]?.dot ?? 'off')

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
  while (true) {
    const full = agentLatestContent.get(task.agent) ?? task.fullContent
    if (pos >= full.length) break
    pos = Math.min(pos + CHARS_PER_TICK, full.length)
    store.messages[actualIdx].content = full.slice(0, pos)
    await nextTick()
    await new Promise<void>((r) => setTimeout(r, TICK_MS))
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

<style scoped lang="scss">
.fm-ai-page {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  position: relative;
}

.fm-ai-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 16px;
  flex: 1;
  min-height: 0;

  &__chat {
    grid-column: 1;
    min-height: 620px;
  }

  &__side {
    grid-column: 2;
    display: flex;
    flex-direction: column;
    gap: 14px;
    min-width: 0;
  }
}

@media (max-width: 1100px) {
  .fm-ai-grid {
    grid-template-columns: 1fr;

    &__chat {
      grid-column: 1;
    }
    &__side {
      grid-column: 1;
    }
  }
}

.fm-ai-head-btn {
  :deep(.el-icon) {
    margin-right: 4px;
  }
}
</style>
