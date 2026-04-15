<template>
  <div class="ai-command-page">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <el-icon class="logo-icon"><Platform /></el-icon>
        <span class="title">AI 智能指挥台</span>
      </div>
      <div class="header-center" v-if="store.currentSessionId">
        <span class="session-badge">Session: {{ store.currentSessionId.slice(0, 8) }}...</span>
      </div>
      <div class="header-right">
        <el-tag
          v-if="store.riskLevel !== 'none'"
          :color="riskColor"
          effect="dark"
          style="border: none; margin-right: 16px;"
        >
          {{ riskLabel }}
        </el-tag>
        <el-button type="primary" plain @click="goBack" class="back-btn">
          <el-icon><Back /></el-icon> 返回
        </el-button>
      </div>
    </header>

    <!-- Main -->
    <main class="main-content">
      <!-- Left: Chat -->
      <ChatPanel :messages="store.messages" :loading="loading" @send="sendQuery" />

      <!-- Right: Sidebar + Session Drawer -->
      <div class="sidebar-wrapper">
        <aside class="sidebar">
          <AgentTimeline :agentStatus="store.agentStatus" />
          <RiskPanel :riskLevel="store.riskLevel" />
          <PlanStatus :planInfo="store.planInfo" />
          <ActiveAlerts />
          <SessionInfo :sessionId="store.currentSessionId" :startTime="startTime" :queryCount="store.queryCount" />
        </aside>
        <SessionDrawer
          ref="sessionDrawerRef"
          v-model="store.drawerOpen"
          :currentSessionId="store.currentSessionId"
          @select="handleSessionSelect"
          @new="handleNewSession"
        />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Platform, Back } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useSSE } from '@/composables/useSSE'
import type { SSEEventType } from '@/composables/useSSE'
import { getStreamUrl } from '@/api/flood'
import { useAiConversationStore, type ChatMessageItem } from '@/stores/aiConversation'

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
  
  // Load session from server
  await store.loadSession(newSessionId)
  startTime.value = new Date().toLocaleTimeString()
  
  // Reset transient state
  typewriterQueue.value = []
  isTyping.value = false
  currentQueryBubbleIdx.clear()
  agentLatestContent.clear()
  reset()
  
  // Update URL
  router.replace({ name: 'AICommandSession', params: { sessionId: newSessionId } })
}

function handleNewSession(newId?: string) {
  store.startNewSession()
  startTime.value = ''
  typewriterQueue.value = []
  isTyping.value = false
  currentQueryBubbleIdx.clear()
  agentLatestContent.clear()
  reset()
  
  // Update URL to base command route
  router.replace({ name: 'AICommand' })
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

// ── Risk state (computed from store) ────────────────────────────
const riskMap: Record<string, { label: string; color: string }> = {
  none:     { label: '正常',   color: '#6b7280' },
  low:      { label: '低风险', color: '#3b82f6' },
  moderate: { label: '中等风险', color: '#f59e0b' },
  high:     { label: '高风险', color: '#ef4444' },
  critical: { label: '极高风险', color: '#7c3aed' },
}
const riskLabel = computed(() => riskMap[store.riskLevel]?.label ?? '正常')
const riskColor = computed(() => riskMap[store.riskLevel]?.color ?? '#6b7280')

// ── Message helpers ─────────────────────────────────────────────
function removeThinkingBubble() {
  const idx = store.messages.findIndex(m => m.role === 'thinking')
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
    if (existing.agentStatus === 'typing') {
      return
    }
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
    await new Promise<void>(r => setTimeout(r, TICK_MS))
  }

  store.messages[actualIdx].agentStatus = 'done'
  processTypewriterQueue()
}

// ── SSE structured events ────────────────────────────────────────
onMounted(async () => {
  // Initialize store from localStorage
  store.initFromLocalStorage()
  
  // Fetch session list
  await store.fetchSessions()
  
  // Check if URL has sessionId param
  const sessionIdFromRoute = route.params.sessionId as string | undefined
  
  if (sessionIdFromRoute) {
    // Load session from URL
    await store.loadSession(sessionIdFromRoute)
    startTime.value = new Date().toLocaleTimeString()
  } else if (store.currentSessionId) {
    // Load previously active session from localStorage
    await store.loadSession(store.currentSessionId)
    startTime.value = new Date().toLocaleTimeString()
  }
  
  // Set up SSE event handlers
  onStructuredEvent((event: SSEEventType) => {
    if (event.type === 'session_init') {
      if (!store.currentSessionId) {
        store.setSessionId(event.sessionId)
        startTime.value = new Date().toLocaleTimeString()
        // Update URL with new session ID
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
        }
      })
    } else if (event.type === 'agent_message') {
      hasAgentMessages.value = true
      enqueueAgentMessage(event.agent, event.content)
    }
  })
})

// ── Keep assistant message in sync with streaming plain-text ────
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

// ── Auto-activate supervisor when loading starts ──────────────────
watch(loading, (isLoading) => {
  if (isLoading) {
    const hasActive = Object.values(store.agentStatus).some(s => s === 'active' || s === 'done')
    if (!hasActive) store.setAgentStatus('supervisor', 'active')
  } else {
    store.finalizeAgentStatuses()
  }
})

// ── Send query ────────────────────────────────────────────────────
async function sendQuery(queryText: string) {
  if (!queryText.trim() || loading.value) return

  // Reset agent statuses
  store.resetAgentStatus()

  // Reset typewriter queue and per-query agent tracking
  hasAgentMessages.value = false
  typewriterQueue.value = []
  isTyping.value = false
  currentQueryBubbleIdx.clear()
  agentLatestContent.clear()

  // Push user message
  store.addMessage({ role: 'user', content: queryText, timestamp: new Date() })

  // Push thinking placeholder
  store.addMessage({ role: 'thinking', content: '正在分析，请稍候…', timestamp: new Date() })

  // Reset SSE accumulator
  reset()

  try {
    const payload: { query: string; sessionId?: string } = { query: queryText }
    if (store.currentSessionId) payload.sessionId = store.currentSessionId
    await start(getStreamUrl(), payload)
    // Refresh session list so title/last-message stays current
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

<style scoped>
.ai-command-page {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: linear-gradient(135deg, #0a1a2e 0%, #162b45 50%, #0d1f33 100%);
  color: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 60px;
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(0, 212, 255, 0.2);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  font-size: 24px;
  color: #00d4ff;
}

.title {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 1px;
}

.session-badge {
  font-family: 'Courier New', Courier, monospace;
  background: rgba(0, 212, 255, 0.1);
  padding: 4px 12px;
  border-radius: 12px;
  border: 1px solid rgba(0, 212, 255, 0.3);
  font-size: 14px;
  color: #00d4ff;
}

.header-right {
  display: flex;
  align-items: center;
}

.back-btn {
  background: transparent;
  border-color: rgba(0, 212, 255, 0.3);
  color: #00d4ff;
}
.back-btn:hover {
  background: rgba(0, 212, 255, 0.1);
  color: #fff;
}

.main-content {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 20px;
  padding: 20px;
  min-height: 0;
  overflow: hidden;
}

.sidebar-wrapper {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  position: relative;
  min-height: 0;
}

/* glass-panel is used by ChatPanel and sidebar sub-components */
:deep(.glass-panel) {
  background: linear-gradient(135deg, rgba(0, 100, 150, 0.1) 0%, rgba(0, 50, 100, 0.05) 100%);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  backdrop-filter: blur(4px);
}

.sidebar {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  padding-right: 4px;
}

.sidebar::-webkit-scrollbar {
  width: 4px;
}
.sidebar::-webkit-scrollbar-thumb {
  background: rgba(0, 212, 255, 0.3);
  border-radius: 4px;
}
</style>
