/** SSE wake stream: instant mobile_active transitions for desktop Kitty poll. */

export const KITTY_DESKTOP_WAKE_STREAM_URL = '/api/kitty/desktop_wake/stream'

export interface KittyDesktopWakeMobileActive {
  type?: unknown
  active?: unknown
  scopes?: unknown
  primary_scope?: unknown
}

export interface KittyDesktopWakeStreamOptions {
  onMobileActive: (payload: KittyDesktopWakeMobileActive) => void
  onOpen?: () => void
  onClose?: () => void
  onError?: (event: Event) => void
}

function parseMobileActivePayload(raw: unknown): KittyDesktopWakeMobileActive | null {
  if (typeof raw !== 'object' || raw === null) {
    return null
  }
  const row = raw as KittyDesktopWakeMobileActive
  if (row.type !== 'mobile_active') {
    return null
  }
  return row
}

/**
 * Opens ``EventSource`` on ``/api/kitty/desktop_wake/stream``. Returns teardown.
 * Reconnects with backoff when the stream drops unexpectedly.
 */
export function createKittyDesktopWakeStream(
  options: KittyDesktopWakeStreamOptions
): () => void {
  if (typeof EventSource === 'undefined') {
    return () => undefined
  }

  let closed = false
  let eventSource: EventSource | null = null
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let retryCount = 0

  function clearRetryTimer(): void {
    if (retryTimer != null) {
      clearTimeout(retryTimer)
      retryTimer = null
    }
  }

  function scheduleReconnect(): void {
    if (closed) {
      return
    }
    clearRetryTimer()
    retryCount += 1
    const delayMs = Math.min(30000, 1000 * retryCount)
    retryTimer = setTimeout(() => {
      retryTimer = null
      connect()
    }, delayMs)
  }

  function connect(): void {
    if (closed) {
      return
    }
    if (eventSource != null) {
      eventSource.close()
      eventSource = null
    }
    eventSource = new EventSource(KITTY_DESKTOP_WAKE_STREAM_URL, { withCredentials: true })
    eventSource.onopen = () => {
      retryCount = 0
      options.onOpen?.()
    }
    eventSource.onmessage = (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(String(event.data)) as unknown
        const payload = parseMobileActivePayload(parsed)
        if (payload != null) {
          options.onMobileActive(payload)
        }
      } catch {
        /* ignore malformed frames */
      }
    }
    eventSource.onerror = (ev: Event) => {
      options.onError?.(ev)
      if (eventSource != null) {
        eventSource.close()
        eventSource = null
      }
      options.onClose?.()
      scheduleReconnect()
    }
  }

  connect()

  return () => {
    closed = true
    clearRetryTimer()
    if (eventSource != null) {
      eventSource.close()
      eventSource = null
    }
    options.onClose?.()
  }
}
