import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getAiAssessments } from '@/api/aiAssessment'
import type { AiAssessment } from '@/types'
import { getToken } from '@/utils/storage'

export type CanonicalRiskLevel = 'none' | 'low' | 'moderate' | 'high' | 'critical'
export type SituationFreshness = 'fresh' | 'stale' | 'none' | 'offline'
export type SituationConnection = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'disconnected'

const ASSESSMENT_FRESH_MS = 30 * 60 * 1000
const FRESHNESS_TICK_MS = 60 * 1000
const PING_INTERVAL_MS = 20 * 1000
const RECONNECT_DELAY_MS = 5 * 1000
const ASSESSMENT_UPDATED_EVENT = 'AI_ASSESSMENT_UPDATED'
const ERROR_EVENT = 'ERROR'
const PONG_EVENT = 'PONG'
const CANONICAL_RISK_LEVELS: CanonicalRiskLevel[] = ['none', 'low', 'moderate', 'high', 'critical']

type AssessmentStreamMessage = {
  type?: string
  data?: unknown
  message?: string
  timestamp?: number
}

function normalizeRiskLevel(level?: string | null): CanonicalRiskLevel {
  const normalized = String(level ?? 'none').trim().toLowerCase()
  if (normalized === 'medium' || normalized === 'warning') {
    return 'moderate'
  }
  if (normalized === 'normal') {
    return 'none'
  }
  return CANONICAL_RISK_LEVELS.includes(normalized as CanonicalRiskLevel)
    ? (normalized as CanonicalRiskLevel)
    : 'none'
}

function isAssessmentFresh(assessment: AiAssessment | null, now = Date.now()): boolean {
  if (!assessment?.assessedAt) return false
  const assessedAtMs = new Date(assessment.assessedAt).getTime()
  if (!Number.isFinite(assessedAtMs)) return false
  return now - assessedAtMs <= ASSESSMENT_FRESH_MS
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message
  }
  return 'Failed to refresh latest AI assessment'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object'
}

function isCompleteAssessmentPayload(value: unknown): value is AiAssessment {
  if (!isRecord(value)) return false
  return (
    typeof value.id === 'string' &&
    typeof value.stationId === 'string' &&
    typeof value.level === 'string' &&
    typeof value.summary === 'string' &&
    typeof value.source === 'string' &&
    typeof value.assessedAt === 'string'
  )
}

function buildAssessmentSocketUrl(path: string): string | null {
  if (typeof window === 'undefined') return null
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const token = getToken()
  const query = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${protocol}//${window.location.host}${path}${query}`
}

export const useSituationStore = defineStore('situation', () => {
  const latestAssessment = ref<AiAssessment | null>(null)
  const lastSyncedAt = ref<string | null>(null)
  const lastError = ref<string | null>(null)
  const isLoading = ref(false)
  const connection = ref<SituationConnection>('idle')

  const nowMs = ref(Date.now())
  const offlineOverride = ref(false)

  let websocket: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let pingInterval: ReturnType<typeof setInterval> | null = null
  let freshnessInterval: ReturnType<typeof setInterval> | null = null
  let streamRequested = false
  let hasConnectedOnce = false

  const canonicalRiskLevel = computed<CanonicalRiskLevel>(() => normalizeRiskLevel(latestAssessment.value?.level))
  const freshness = computed<SituationFreshness>(() => {
    if (offlineOverride.value) return 'offline'
    if (!latestAssessment.value) return 'none'
    return isAssessmentFresh(latestAssessment.value, nowMs.value) ? 'fresh' : 'stale'
  })

  function ensureFreshnessTicker() {
    if (freshnessInterval) return
    freshnessInterval = setInterval(() => {
      nowMs.value = Date.now()
    }, FRESHNESS_TICK_MS)
  }

  function stopFreshnessTicker() {
    if (!freshnessInterval) return
    clearInterval(freshnessInterval)
    freshnessInterval = null
  }

  function stopPingInterval() {
    if (!pingInterval) return
    clearInterval(pingInterval)
    pingInterval = null
  }

  function startPingInterval() {
    stopPingInterval()
    pingInterval = setInterval(() => {
      if (websocket?.readyState === WebSocket.OPEN) {
        websocket.send('ping')
      }
    }, PING_INTERVAL_MS)
  }

  function clearReconnectTimer() {
    if (!reconnectTimer) return
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }

  function applyAssessment(assessment: AiAssessment | null, options?: { syncedAt?: string | null; clearError?: boolean }) {
    latestAssessment.value = assessment
    nowMs.value = Date.now()

    if (options?.syncedAt !== undefined) {
      lastSyncedAt.value = options.syncedAt
    }

    if (options?.clearError) {
      lastError.value = null
      offlineOverride.value = false
    }
  }

  async function refreshLatestAssessment() {
    ensureFreshnessTicker()
    isLoading.value = true

    try {
      const res = await getAiAssessments({ limit: 1 })
      applyAssessment(res.data?.[0] ?? null, {
        syncedAt: new Date().toISOString(),
        clearError: true,
      })
      return latestAssessment.value
    } catch (error) {
      lastError.value = getErrorMessage(error)
      offlineOverride.value = true
      nowMs.value = Date.now()
      return latestAssessment.value
    } finally {
      isLoading.value = false
    }
  }

  async function ensureFresh() {
    ensureFreshnessTicker()
    if (!latestAssessment.value || freshness.value !== 'fresh') {
      await refreshLatestAssessment()
    }
  }

  function cleanupSocket(options?: { keepRequested?: boolean; resetConnection?: SituationConnection }) {
    const nextConnection = options?.resetConnection ?? 'disconnected'
    const keepRequested = options?.keepRequested ?? false

    clearReconnectTimer()
    stopPingInterval()

    const socket = websocket
    websocket = null

    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.close()
    } else if (socket && socket.readyState === WebSocket.CONNECTING) {
      socket.close()
    }

    connection.value = nextConnection
    if (!keepRequested) {
      streamRequested = false
    }
  }

  function scheduleReconnect() {
    if (!streamRequested || reconnectTimer) return
    connection.value = 'reconnecting'
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      openAssessmentStream()
    }, RECONNECT_DELAY_MS)
  }

  function handleSocketMessage(raw: string) {
    let payload: AssessmentStreamMessage

    try {
      payload = JSON.parse(raw) as AssessmentStreamMessage
    } catch {
      return
    }

    if (payload.type === PONG_EVENT) {
      return
    }

    if (payload.type === ERROR_EVENT) {
      lastError.value = typeof payload.message === 'string' ? payload.message : 'AI assessment stream error'
      return
    }

    if (payload.type === ASSESSMENT_UPDATED_EVENT) {
      if (isCompleteAssessmentPayload(payload.data)) {
        applyAssessment(payload.data, {
          syncedAt: new Date().toISOString(),
          clearError: true,
        })
        return
      }

      void refreshLatestAssessment()
    }
  }

  function openAssessmentStream() {
    const url = buildAssessmentSocketUrl('/ws/ai-assessments')
    if (!url) {
      connection.value = 'disconnected'
      return
    }

    if (websocket && (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)) {
      return
    }

    connection.value = hasConnectedOnce ? 'reconnecting' : 'connecting'

    const socket = new WebSocket(url)
    websocket = socket

    socket.onopen = () => {
      if (websocket !== socket) return
      hasConnectedOnce = true
      connection.value = 'connected'
      lastError.value = null
      startPingInterval()
    }

    socket.onmessage = (event) => {
      if (websocket !== socket) return
      if (typeof event.data === 'string') {
        handleSocketMessage(event.data)
      }
    }

    socket.onerror = () => {
      if (websocket !== socket) return
      lastError.value = 'AI assessment stream connection error'
    }

    socket.onclose = () => {
      if (websocket !== socket) return
      websocket = null
      stopPingInterval()

      if (!streamRequested) {
        connection.value = 'disconnected'
        return
      }

      scheduleReconnect()
    }
  }

  function connectAssessmentStream() {
    ensureFreshnessTicker()
    streamRequested = true

    if (websocket && (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)) {
      return
    }

    if (reconnectTimer) {
      return
    }

    openAssessmentStream()
  }

  function resetForTest() {
    cleanupSocket({ resetConnection: 'idle' })
    stopFreshnessTicker()

    latestAssessment.value = null
    lastSyncedAt.value = null
    lastError.value = null
    isLoading.value = false
    connection.value = 'idle'
    nowMs.value = Date.now()
    offlineOverride.value = false
    hasConnectedOnce = false
  }

  ensureFreshnessTicker()

  return {
    latestAssessment,
    canonicalRiskLevel,
    freshness,
    connection,
    lastSyncedAt,
    lastError,
    isLoading,
    refreshLatestAssessment,
    ensureFresh,
    connectAssessmentStream,
    resetForTest,
  }
})
