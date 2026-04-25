import { ref, onUnmounted } from 'vue'
import { getToken } from '@/utils/storage'

export function useWebSocket(path: string) {
  const MAX_MESSAGES = 100 // Limit messages to prevent memory leak
  const messages = ref<any[]>([])
  const connected = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let manuallyClosed = false

  function connect() {
    manuallyClosed = false
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const token = getToken()
    const url = `${protocol}//${host}${path}${token ? `?token=${token}` : ''}`

    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        messages.value.push(data)
        // Keep message list bounded to prevent memory leak
        if (messages.value.length > MAX_MESSAGES) {
          messages.value.shift()
        }
      } catch {
        messages.value.push(event.data)
        if (messages.value.length > MAX_MESSAGES) {
          messages.value.shift()
        }
      }
    }

    ws.onclose = () => {
      connected.value = false
      if (!manuallyClosed) {
        reconnectTimer = setTimeout(connect, 5000)
      }
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function send(data: any) {
    if (ws && connected.value) {
      ws.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }

  function disconnect() {
    manuallyClosed = true
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
    ws = null
    connected.value = false
  }

  function clearMessages() {
    messages.value = []
  }

  onUnmounted(disconnect)

  return { messages, connected, connect, send, disconnect, clearMessages }
}
