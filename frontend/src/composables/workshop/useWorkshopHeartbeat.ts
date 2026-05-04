/**
 * Workshop WebSocket application-level heartbeat (ping frames) with jitter,
 * half-open detection (pong deadline), and visibility-aware wake pings.
 */
import type { Ref } from 'vue'

/** Ping interval target — uniform jitter in ``[-JITTER_MS, +JITTER_MS]`` applied per schedule. */
const HEARTBEAT_BASE_MS = 30_000
const HEARTBEAT_JITTER_MS = 5_000
/** Close the socket if no ``pong`` arrives this long after a ``ping`` sent. */
const PONG_DEADLINE_MS = 10_000

export function useWorkshopHeartbeat(ws: Ref<WebSocket | null>, isConnected: Ref<boolean>) {
  let heartbeatTimeout: ReturnType<typeof setTimeout> | null = null
  let pongDeadlineTimer: ReturnType<typeof setTimeout> | null = null
  let visibilityHandler: (() => void) | null = null

  function clearPongDeadline(): void {
    if (pongDeadlineTimer !== null) {
      clearTimeout(pongDeadlineTimer)
      pongDeadlineTimer = null
    }
  }

  function armPongDeadline(): void {
    clearPongDeadline()
    const sock = ws.value
    if (!sock || sock.readyState !== WebSocket.OPEN) {
      return
    }
    const socketRef = sock
    pongDeadlineTimer = setTimeout(() => {
      pongDeadlineTimer = null
      if (socketRef.readyState === WebSocket.OPEN) {
        try {
          socketRef.close(4000, 'pong_timeout')
        } catch {
          /* ignore */
        }
      }
    }, PONG_DEADLINE_MS)
  }

  function recordPong(): void {
    clearPongDeadline()
  }

  function nextHeartbeatDelayMs(): number {
    const jitter = (Math.random() * 2 - 1) * HEARTBEAT_JITTER_MS
    return Math.max(5_000, Math.round(HEARTBEAT_BASE_MS + jitter))
  }

  function scheduleNextHeartbeat(): void {
    if (heartbeatTimeout !== null) {
      clearTimeout(heartbeatTimeout)
      heartbeatTimeout = null
    }
    heartbeatTimeout = setTimeout(() => {
      heartbeatTimeout = null
      ping()
      scheduleNextHeartbeat()
    }, nextHeartbeatDelayMs())
  }

  function ping(): void {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      return
    }

    try {
      ws.value.send(JSON.stringify({ type: 'ping' }))
      armPongDeadline()
    } catch (error) {
      if (import.meta.env.DEV) {
        console.debug('[WorkshopWS] Failed to send ping:', error)
      }
    }
  }

  function startHeartbeat(): void {
    if (heartbeatTimeout !== null) {
      clearTimeout(heartbeatTimeout)
      heartbeatTimeout = null
    }
    if (typeof document !== 'undefined' && visibilityHandler === null) {
      visibilityHandler = () => {
        if (document.visibilityState === 'visible' && isConnected.value) {
          ping()
        }
      }
      document.addEventListener('visibilitychange', visibilityHandler)
    }
    ping()
    scheduleNextHeartbeat()
  }

  function stopHeartbeat(): void {
    if (heartbeatTimeout !== null) {
      clearTimeout(heartbeatTimeout)
      heartbeatTimeout = null
    }
    clearPongDeadline()
    if (typeof document !== 'undefined' && visibilityHandler !== null) {
      document.removeEventListener('visibilitychange', visibilityHandler)
      visibilityHandler = null
    }
  }

  return { ping, startHeartbeat, stopHeartbeat, recordPong }
}
