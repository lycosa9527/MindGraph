/** Desktop WebSocket: event wake when a 演讲模式 watch click is queued. */

export const SLIDE_REMOTE_WAKE_WS_PATH = '/api/ws/slides-remote'
export const SLIDE_REMOTE_COMMAND_PENDING_TYPE = 'slides_command_pending'

export interface SlideRemoteWakeSocketOptions {
  onCommandPending: () => void
  onOpen?: () => void
  onClose?: () => void
  shouldReconnect?: () => boolean
}

export function buildSlideRemoteWakeWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}${SLIDE_REMOTE_WAKE_WS_PATH}`
}

function isCommandPending(raw: unknown): boolean {
  if (typeof raw !== 'object' || raw === null) {
    return false
  }
  return (raw as { type?: unknown }).type === SLIDE_REMOTE_COMMAND_PENDING_TYPE
}

/**
 * Opens ``/api/ws/slides-remote``. Returns teardown.
 * Reconnects with backoff when the socket drops unexpectedly.
 */
export function createSlideRemoteWakeSocket(options: SlideRemoteWakeSocketOptions): () => void {
  if (typeof WebSocket === 'undefined') {
    return () => undefined
  }

  let closed = false
  let socket: WebSocket | null = null
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let retryCount = 0

  function clearRetryTimer(): void {
    if (retryTimer != null) {
      clearTimeout(retryTimer)
      retryTimer = null
    }
  }

  /** Drop handlers before ``close()`` so teardown / replace cannot re-enter ``onclose``. */
  function detachSocket(): void {
    const current = socket
    socket = null
    if (current == null) {
      return
    }
    current.onerror = null
    current.onopen = null
    current.onmessage = null
    current.onclose = null
    current.close()
  }

  function scheduleReconnect(): void {
    if (closed) {
      return
    }
    if (options.shouldReconnect != null && !options.shouldReconnect()) {
      return
    }
    clearRetryTimer()
    retryCount += 1
    const delayMs = Math.min(30000, 1000 * retryCount)
    retryTimer = setTimeout(() => {
      retryTimer = null
      if (closed) {
        return
      }
      if (options.shouldReconnect != null && !options.shouldReconnect()) {
        return
      }
      connect()
    }, delayMs)
  }

  function handleFrame(raw: string): void {
    let parsed: unknown
    try {
      parsed = JSON.parse(raw)
    } catch {
      return
    }
    if (typeof parsed === 'object' && parsed !== null) {
      const row = parsed as { type?: unknown }
      if (row.type === 'ping') {
        socket?.send(JSON.stringify({ type: 'pong' }))
        return
      }
    }
    if (isCommandPending(parsed)) {
      options.onCommandPending()
    }
  }

  function connect(): void {
    if (closed) {
      return
    }
    detachSocket()
    socket = new WebSocket(buildSlideRemoteWakeWsUrl())
    socket.onopen = () => {
      retryCount = 0
      options.onOpen?.()
    }
    socket.onmessage = (event: MessageEvent) => {
      handleFrame(String(event.data))
    }
    socket.onerror = () => {
      /* onclose handles reconnect */
    }
    socket.onclose = () => {
      if (closed) {
        return
      }
      socket = null
      options.onClose?.()
      scheduleReconnect()
    }
  }

  connect()

  return () => {
    closed = true
    clearRetryTimer()
    detachSocket()
  }
}
