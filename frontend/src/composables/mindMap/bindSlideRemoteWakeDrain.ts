/**
 * Desktop 演讲模式 command intake: WebSocket wake + instant LPOP.
 * No interval poll. Drain only on connect and on ``slides_command_pending``.
 */
import { createSlideRemoteWakeSocket } from '@/composables/mindMap/createSlideRemoteWakeSocket'

export function bindSlideRemoteWakeDrain(options: {
  drain: () => Promise<void>
  shouldRun: () => boolean
}): {
  start: () => void
  stop: () => void
} {
  let stopWake: (() => void) | null = null
  let wakeConnected = false

  function stopWakeSocket(): void {
    if (stopWake != null) {
      stopWake()
      stopWake = null
    }
    wakeConnected = false
  }

  function startWakeSocket(): void {
    if (stopWake != null && wakeConnected) {
      return
    }
    stopWakeSocket()
    if (!options.shouldRun()) {
      return
    }
    stopWake = createSlideRemoteWakeSocket({
      shouldReconnect: () => options.shouldRun(),
      onCommandPending: () => {
        void options.drain()
      },
      onOpen: () => {
        wakeConnected = true
        void options.drain()
      },
      onClose: () => {
        wakeConnected = false
      },
    })
  }

  function start(): void {
    if (!options.shouldRun()) {
      stop()
      return
    }
    if (stopWake != null) {
      return
    }
    void options.drain()
    startWakeSocket()
  }

  function stop(): void {
    stopWakeSocket()
  }

  return { start, stop }
}
