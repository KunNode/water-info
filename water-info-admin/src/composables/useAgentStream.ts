import { ref, onUnmounted } from 'vue'
import { getToken, getUserInfo } from '@/utils/storage'
import type { AgentStreamEvent } from '@/types/agentStream'
import type { UserInfo } from '@/types'

export interface ParsedSSEMessage {
  event?: string
  data: string
  id?: string
}

export function useAgentStream() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const events = ref<AgentStreamEvent[]>([])
  const plainText = ref('')
  let controller: AbortController | null = null
  let eventHandler: ((event: AgentStreamEvent) => void) | null = null
  let textHandler: ((text: string) => void) | null = null

  function onEvent(cb: (event: AgentStreamEvent) => void) {
    eventHandler = cb
  }

  function onText(cb: (text: string) => void) {
    textHandler = cb
  }

  async function start(url: string, body: unknown) {
    reset()
    loading.value = true
    controller = new AbortController()

    try {
      const user = getUserInfo<UserInfo>()
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
          ...(user?.id ? { 'X-User-Id': user.id } : {}),
          ...(user?.username ? { 'X-Username': user.username } : {}),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      if (!response.body) throw new Error('No readable stream')

      await readEventStream(response.body)
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        const message = err.message || '流式请求失败'
        error.value = message
        emitEvent({ type: 'error', message, recoverable: false })
      }
    } finally {
      loading.value = false
    }
  }

  async function readEventStream(stream: ReadableStream<Uint8Array>) {
    const reader = stream.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    let streamDone = false
    while (!streamDone) {
      const { done, value } = await reader.read()
      streamDone = done
      if (streamDone) break
      buffer += decoder.decode(value, { stream: true })

      const parts = buffer.split(/\r?\n\r?\n/)
      buffer = parts.pop() ?? ''
      for (const part of parts) {
        dispatchSSEMessage(parseSSEMessage(part))
      }

      if (buffer && !looksLikeSSEFragment(buffer)) {
        emitText(buffer)
        buffer = ''
      }
    }

    buffer += decoder.decode()
    if (buffer.trim()) dispatchSSEMessage(parseSSEMessage(buffer))
  }

  function parseSSEMessage(raw: string): ParsedSSEMessage {
    const message: ParsedSSEMessage = { data: '' }
    const lines = raw.split(/\r?\n/)

    for (const line of lines) {
      if (!line || line.startsWith(':')) continue
      const idx = line.indexOf(':')
      const field = idx >= 0 ? line.slice(0, idx) : line
      const value = idx >= 0 ? line.slice(idx + 1).replace(/^ /, '') : ''

      if (field === 'event') message.event = value
      if (field === 'id') message.id = value
      if (field === 'data') message.data += message.data ? `\n${value}` : value
    }

    const isCommentOnly = lines.every(line => {
      const trimmed = line.trimStart()
      return !trimmed || trimmed.startsWith(':')
    })
    if (!message.data && raw.trim() && !isCommentOnly) message.data = raw.trim()
    return message
  }

  function dispatchSSEMessage(message: ParsedSSEMessage) {
    const payload = normalizePayload(message.data)
    if (!payload || payload === '[DONE]') return

    const parsed = parsePayload(payload, message.event)
    if (parsed) {
      emitEvent(parsed)
      return
    }

    emitText(payload)
  }

  function normalizePayload(payload: string) {
    let normalized = payload.trim()
    if (normalized.startsWith(':')) return ''
    while (normalized.startsWith('data:')) {
      normalized = normalized.slice(5).trim()
    }
    return normalized
  }

  function parsePayload(payload: string, eventName?: string): AgentStreamEvent | null {
    try {
      const parsed = JSON.parse(payload)
      if (typeof parsed === 'string') return parsePayload(parsed, eventName)
      if (parsed && typeof parsed === 'object') {
        const value = parsed as Record<string, unknown>
        if (!value.type && eventName) value.type = eventName
        if (typeof value.type === 'string') return value as AgentStreamEvent
      }
    } catch {
      if (eventName) {
        return {
          type: eventName,
          delta: payload,
        } as AgentStreamEvent
      }
    }
    return null
  }

  function looksLikeSSEFragment(buffer: string) {
    const trimmed = buffer.trimStart()
    return (
      trimmed.startsWith('event:') ||
      trimmed.startsWith('data:') ||
      trimmed.startsWith('id:') ||
      trimmed.startsWith(':') ||
      trimmed.startsWith('{') ||
      trimmed.startsWith('[') ||
      trimmed.startsWith('"')
    )
  }

  function emitEvent(event: AgentStreamEvent) {
    events.value.push(event)
    eventHandler?.(event)
  }

  function emitText(text: string) {
    if (!text) return
    plainText.value += text
    textHandler?.(text)
  }

  function stop() {
    controller?.abort()
    loading.value = false
  }

  function reset() {
    error.value = null
    events.value = []
    plainText.value = ''
  }

  onUnmounted(stop)

  return { loading, error, events, plainText, start, stop, reset, onEvent, onText }
}
