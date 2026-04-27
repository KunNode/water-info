import { ref, onUnmounted } from 'vue'
import { getToken } from '@/utils/storage'

export type SSEEventType =
  | { type: 'agent_update'; agent: string; status: 'active' | 'done' | 'failed' }
  | { type: 'risk_update'; level: string; details?: string[] }
  | { type: 'plan_update'; name: string; status: string; total: number; completed: number; failed: number }
  | { type: 'session_init'; sessionId: string }
  | { type: 'agent_message'; agent: string; content: string }
  | {
      type: 'evidence_update'
      agent: string
      items: Array<{
        citation_id: string
        content: string
        document_title: string
        source_uri?: string
        heading_path?: string[]
        score?: number
      }>
    }

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

  function pushPlainText(text: string) {
    if (!text) return
    chunks.value.push(text)
    fullText.value += text
    if (chunks.value.length > MAX_CHUNKS) {
      chunks.value.shift()
    }
  }

  function dispatchStructuredEvent(payload: string): boolean {
    let normalized = payload.trim()
    if (!normalized || normalized === '[DONE]') return true

    // Some proxy layers may forward already-prefixed SSE payloads again.
    while (normalized.startsWith('data:')) {
      normalized = normalized.slice(5).trim()
    }
    if (!normalized || normalized === '[DONE]') return true

    const emitIfStructured = (value: unknown) => {
      if (value && typeof value === 'object' && 'type' in value) {
        const event = value as SSEEventType
        structuredEvents.value.push(event)
        onEvent?.(event)
        return true
      }
      return false
    }

    try {
      const parsed = JSON.parse(normalized)
      if (typeof parsed === 'string') {
        normalized = parsed.trim()
        if (!normalized || normalized === '[DONE]') return true
      } else if (emitIfStructured(parsed)) {
        return true
      } else {
        return false
      }
    } catch {
      // Fall through and let the caller decide whether this is plain text
      // or an incomplete fragment that needs more bytes.
    }

    try {
      return emitIfStructured(JSON.parse(normalized))
    } catch {
      return false
    }
  }

  function flushChunk(chunk: string) {
    const trimmed = chunk.trim()
    if (!trimmed) return

    const dataLines = chunk
      .split(/\r?\n/)
      .map(line => line.trimEnd())
      .filter(line => line.startsWith('data:'))

    if (dataLines.length > 0) {
      const payload = dataLines
        .map(line => line.slice(5).trim())
        .join('\n')

      if (!dispatchStructuredEvent(payload)) {
        pushPlainText(payload)
      }
      return
    }

    if (!dispatchStructuredEvent(trimmed)) {
      pushPlainText(chunk)
    }
  }

  function looksLikeStructuredFragment(buffer: string) {
    const trimmed = buffer.trimStart()
    return (
      trimmed.startsWith('data:') ||
      trimmed.startsWith('event:') ||
      trimmed.startsWith('{') ||
      trimmed.startsWith('[') ||
      trimmed.startsWith('"')
    )
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

      // Keep incomplete fragments between reads so structured SSE blocks can
      // span network chunks, while still allowing raw text streams to render
      // incrementally even when the backend does not emit newline delimiters.
      let buffer = ''

      let streamDone = false
      while (!streamDone) {
        const { done, value } = await reader.read()
        streamDone = done
        if (streamDone) break

        buffer += decoder.decode(value, { stream: true })

        let blockEnd = buffer.search(/\r?\n\r?\n/)
        while (blockEnd >= 0) {
          const block = buffer.slice(0, blockEnd)
          flushChunk(block)
          buffer = buffer.slice(blockEnd).replace(/^\r?\n\r?\n/, '')
          blockEnd = buffer.search(/\r?\n\r?\n/)
        }

        if (buffer && !looksLikeStructuredFragment(buffer)) {
          pushPlainText(buffer)
          buffer = ''
        }
      }

      // Flush any remaining buffered content after stream closes.
      if (buffer) flushChunk(buffer)
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
