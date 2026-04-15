import { ref, onUnmounted } from 'vue'
import { getToken } from '@/utils/storage'

export type SSEEventType =
  | { type: 'agent_update'; agent: string; status: 'active' | 'done' | 'failed' }
  | { type: 'risk_update'; level: string; details?: string[] }
  | { type: 'plan_update'; name: string; status: string; total: number; completed: number; failed: number }
  | { type: 'session_init'; sessionId: string }
  | { type: 'agent_message'; agent: string; content: string }

export function useSSE() {
  const MAX_CHUNKS = 100
  const chunks = ref<string[]>([])
  const fullText = ref('')
  const loading = ref(false)
  const error = ref<string | null>(null)
  const structuredEvents = ref<SSEEventType[]>([])
  let controller: AbortController | null = null

  // Callback invoked immediately when a structured event arrives (for real-time UI updates)
  let onEvent: ((event: SSEEventType) => void) | null = null

  function onStructuredEvent(cb: (event: SSEEventType) => void) {
    onEvent = cb
  }

  async function start(url: string, body: any) {
    chunks.value = []
    fullText.value = ''
    loading.value = true
    error.value = null
    structuredEvents.value = []

    controller = new AbortController()
    const token = getToken()

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) throw new Error('No readable stream')

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value, { stream: true })
        const lines = text.split('\n')

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue

          const data = line.slice(6).trim()
          if (data === '[DONE]') continue
          if (!data) continue

          // Try to parse as structured JSON event
          if (data.startsWith('{')) {
            try {
              const parsed = JSON.parse(data) as SSEEventType
              if (parsed.type) {
                structuredEvents.value.push(parsed)
                onEvent?.(parsed)
                continue
              }
            } catch {
              // Not valid JSON, fall through to treat as text
            }
          }

          // Plain text chunk
          chunks.value.push(data)
          fullText.value += data
          if (chunks.value.length > MAX_CHUNKS) {
            chunks.value.shift()
          }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        error.value = err.message
      }
    } finally {
      loading.value = false
    }
  }

  function stop() {
    controller?.abort()
    loading.value = false
  }

  function reset() {
    chunks.value = []
    fullText.value = ''
    error.value = null
    structuredEvents.value = []
  }

  onUnmounted(stop)

  return { chunks, fullText, loading, error, structuredEvents, start, stop, reset, onStructuredEvent }
}
