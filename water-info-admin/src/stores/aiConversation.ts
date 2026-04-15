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
import {
  listConversations,
  getConversation,
  getConversationMessages,
  deleteConversation as apiDeleteConversation,
  renameConversation as apiRenameConversation,
} from '@/api/flood'

export interface ChatMessageItem {
  id?: number
  role: 'user' | 'assistant' | 'thinking' | 'agent'
  content: string
  timestamp: Date
  agent?: string
  agentStatus?: 'typing' | 'done' | 'pending'
}

export interface PlanInfo {
  name: string
  status: string
  total: number
  completed: number
  failed: number
}

const LOCAL_STORAGE_KEYS = {
  CURRENT_SESSION_ID: 'water_ai_current_session_id',
  INPUT_DRAFT: 'water_ai_input_draft',
  DRAWER_OPEN: 'water_ai_drawer_open',
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

  // ── Agent timeline state (transient, not persisted) ───────────────
  const agentStatus = ref<Record<string, string>>({
    supervisor: 'pending',
    data_analyst: 'pending',
    risk_assessor: 'pending',
    plan_generator: 'pending',
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
  async function loadSession(sessionId: string) {
    if (!sessionId) {
      clearCurrentSession()
      return
    }

    isLoadingSession.value = true
    try {
      // Load messages with snapshot
      const res = await getConversationMessages(sessionId)
      const detail = res.data

      currentSessionId.value = sessionId
      sessionTitle.value = detail?.title ?? ''
      snapshot.value = detail?.snapshot ?? null

      // Convert server messages to ChatMessageItem format
      messages.value = (detail?.messages ?? []).map<ChatMessageItem>(m => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        timestamp: m.created_at ? new Date(m.created_at) : new Date(),
      }))

      persistToLocalStorage()
    } catch (e) {
      console.error('[AI Store] Failed to load session:', e)
      clearCurrentSession()
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
    resetAgentStatus()
    persistToLocalStorage()
  }

  // ── Clear current session state ───────────────────────────────────
  function clearCurrentSession() {
    currentSessionId.value = ''
    sessionTitle.value = ''
    messages.value = []
    snapshot.value = null
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
    removeThinkingMessage,
    deleteSession,
    renameSession,
    setInputDraft,
    toggleDrawer,
    setDrawerOpen,
  }
})
