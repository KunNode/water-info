<template>
  <div class="ai-command-page">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <el-icon class="logo-icon"><Platform /></el-icon>
        <span class="title">AI 智能指挥台</span>
      </div>
      <div class="header-center" v-if="sessionId">
        <span class="session-badge">Session: {{ sessionId.slice(0, 8) }}...</span>
      </div>
      <div class="header-right">
        <el-tag
          v-if="riskLevel !== 'none'"
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
      <ChatPanel :messages="messages" :loading="loading" @send="sendQuery" />

      <!-- Right: Sidebar -->
      <aside class="sidebar">
        <AgentTimeline :agentStatus="agentStatus" />
        <RiskPanel :riskLevel="riskLevel" />
        <PlanStatus :planInfo="planInfo" />
        <ActiveAlerts />
        <SessionInfo :sessionId="sessionId" :startTime="startTime" :queryCount="queryCount" />
      </aside>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Platform, Back } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useSSE } from '@/composables/useSSE'
import type { SSEEventType } from '@/composables/useSSE'
import { getStreamUrl } from '@/api/flood'

// Sub-components
import ChatPanel from './components/ChatPanel.vue'
import AgentTimeline from './components/AgentTimeline.vue'
import RiskPanel from './components/RiskPanel.vue'
import PlanStatus from './components/PlanStatus.vue'
import ActiveAlerts from './components/ActiveAlerts.vue'
import SessionInfo from './components/SessionInfo.vue'
import type { ChatMessageItem } from './components/ChatMessage.vue'

const router = useRouter()
const { fullText, loading, error, start, stop, reset, onStructuredEvent } = useSSE()

// ── Conversation state ──────────────────────────────────────────
const messages = ref<ChatMessageItem[]>([])

// ── Session state ───────────────────────────────────────────────
const sessionId = ref('')
const startTime = ref('')
const queryCount = ref(0)

// ── Agent timeline ──────────────────────────────────────────────
const agentStatus = reactive<Record<string, string>>({
  supervisor: 'pending',
  data_analyst: 'pending',
  risk_assessor: 'pending',
  plan_generator: 'pending',
  resource_dispatcher: 'pending',
  notification: 'pending',
})

// ── Typewriter queue ─────────────────────────────────────────────
interface TypewriterTask {
  agent: string
  fullContent: string
}

const typewriterQueue = ref<TypewriterTask[]>([])
const isTyping = ref(false)
const CHARS_PER_TICK = 4
const TICK_MS = 16

// Maps agent name → messages array index for the current query.
// Cleared on each new sendQuery so cross-query dedup doesn't happen.
const currentQueryBubbleIdx = new Map<string, number>()

// Latest known full content per agent — updated on each agent_message event
// so the typewriter loop always types up to the most recent content.
const agentLatestContent = new Map<string, string>()

// Remove the "分析中..." thinking placeholder on first real content
function removeThinkingBubble() {
  const idx = messages.value.findIndex(m => m.role === 'thinking')
  if (idx >= 0) {
    messages.value.splice(idx, 1)
    // All currentQueryBubbleIdx entries that were recorded after the removed
    // bubble need their index decremented by 1.
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
    const existing = messages.value[existingIdx]
    if (existing.agentStatus === 'typing') {
      // Typewriter is already running — agentLatestContent is already updated,
      // the loop will pick up the new target on the next tick. Nothing else to do.
      return
    }
    // Bubble is done — silently replace content (no re-animation to avoid flash)
    existing.content = content
    return
  }

  // First message for this agent in this query — create a new bubble
  const idx = messages.value.length
  currentQueryBubbleIdx.set(agent, idx)
  messages.value.push({
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

  // Type characters — always read the latest known content so mid-stream
  // updates (agentLatestContent) are picked up without restarting from zero.
  let pos = messages.value[actualIdx].content.length
  while (true) {
    const full = agentLatestContent.get(task.agent) ?? task.fullContent
    if (pos >= full.length) break
    pos = Math.min(pos + CHARS_PER_TICK, full.length)
    messages.value[actualIdx].content = full.slice(0, pos)
    await nextTick()
    await new Promise<void>(r => setTimeout(r, TICK_MS))
  }

  // Mark done
  messages.value[actualIdx].agentStatus = 'done'

  processTypewriterQueue()
}

// ── Risk state ──────────────────────────────────────────────────
const riskLevel = ref('none')
const riskMap: Record<string, { label: string; color: string }> = {
  none:     { label: '正常',   color: '#6b7280' },
  low:      { label: '低风险', color: '#3b82f6' },
  moderate: { label: '中等风险', color: '#f59e0b' },
  high:     { label: '高风险', color: '#ef4444' },
  critical: { label: '极高风险', color: '#7c3aed' },
}
const riskLabel = computed(() => riskMap[riskLevel.value]?.label ?? '正常')
const riskColor = computed(() => riskMap[riskLevel.value]?.color ?? '#6b7280')

// ── Plan state ──────────────────────────────────────────────────
interface PlanInfo {
  name: string
  status: string
  total: number
  completed: number
  failed: number
}
const planInfo = ref<PlanInfo | null>(null)

// ── SSE structured events ────────────────────────────────────────
onMounted(() => {
  onStructuredEvent((event: SSEEventType) => {
    if (event.type === 'session_init') {
      if (!sessionId.value) {
        sessionId.value = event.sessionId
        startTime.value = new Date().toLocaleTimeString()
      }
    } else if (event.type === 'agent_update') {
      agentStatus[event.agent] = event.status
    } else if (event.type === 'risk_update') {
      riskLevel.value = event.level
    } else if (event.type === 'plan_update') {
      planInfo.value = {
        name: event.name,
        status: event.status,
        total: event.total,
        completed: event.completed,
        failed: event.failed,
      }
    } else if (event.type === 'agent_message') {
      enqueueAgentMessage(event.agent, event.content)
    }
  })
})

// ── Keep assistant message in sync with streaming plain-text ────
// Lazily create the assistant bubble on the first non-empty chunk so that
// queries answered entirely via agent_message events leave no ghost placeholder.
watch(fullText, (val) => {
  if (!val) return
  removeThinkingBubble()
  const last = messages.value[messages.value.length - 1]
  if (last?.role === 'assistant') {
    last.content = val
  } else {
    messages.value.push({ role: 'assistant', content: val, timestamp: new Date() })
  }
})

// ── Auto-activate supervisor when loading starts ──────────────────
watch(loading, (isLoading) => {
  if (isLoading) {
    const hasActive = Object.values(agentStatus).some(s => s === 'active' || s === 'done')
    if (!hasActive) agentStatus.supervisor = 'active'
  } else {
    Object.keys(agentStatus).forEach(key => {
      if (agentStatus[key] === 'active') agentStatus[key] = 'done'
    })
  }
})

// ── Send query ────────────────────────────────────────────────────
async function sendQuery(queryText: string) {
  if (!queryText.trim() || loading.value) return

  queryCount.value++

  // Reset agent statuses
  Object.keys(agentStatus).forEach(key => { agentStatus[key] = 'pending' })

  // Reset typewriter queue and per-query agent tracking
  typewriterQueue.value = []
  isTyping.value = false
  currentQueryBubbleIdx.clear()
  agentLatestContent.clear()

  // Push user message
  messages.value.push({ role: 'user', content: queryText, timestamp: new Date() })

  // Push thinking placeholder — removed automatically on first real content
  messages.value.push({ role: 'thinking', content: '正在分析，请稍候…', timestamp: new Date() })

  // Reset SSE accumulator
  reset()

  try {
    const payload: { query: string; sessionId?: string } = { query: queryText }
    if (sessionId.value) payload.sessionId = sessionId.value
    await start(getStreamUrl(), payload)
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
  grid-template-columns: 1fr 300px;
  gap: 20px;
  padding: 20px;
  min-height: 0;
  overflow: hidden;
}

/* glass-panel is used by ChatPanel and sidebar sub-components */
:deep(.glass-panel) {
  background: linear-gradient(135deg, rgba(0, 100, 150, 0.1) 0%, rgba(0, 50, 100, 0.05) 100%);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  backdrop-filter: blur(4px);
}

.sidebar {
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
