/** SSE wake stream: instant mobile_active transitions for desktop Kitty poll. */
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'

export const KITTY_DESKTOP_WAKE_STREAM_URL = '/api/kitty/desktop_wake/stream'

export interface KittyDesktopWakeMobileActive {
  type?: unknown
  active?: unknown
  scopes?: unknown
  primary_scope?: unknown
}

export interface KittyDesktopWakeStreamOptions {
  onMobileActive: (payload: KittyDesktopWakeMobileActive) => void
  onDesktopActionPending?: () => void
  onDiagramUpdate?: (payload: KittyDesktopDiagramUpdateFanout) => void
  onSelectionUpdate?: (payload: KittyDesktopSelectionUpdateFanout) => void
  onLlmModelUpdate?: (payload: KittyDesktopLlmModelUpdateFanout) => void
  onVoiceCommand?: (payload: KittyDesktopVoiceCommandFanout) => void
  onVoicePhaseUpdate?: (payload: KittyDesktopVoicePhaseUpdateFanout) => void
  onOpen?: () => void
  onClose?: () => void
  onError?: (event: Event) => void
}

export interface KittyDesktopDiagramUpdateFanout {
  type?: unknown
  scope?: unknown
  action?: unknown
  updates?: unknown
  mutation_id?: unknown
}

export interface KittyDesktopSelectionUpdateFanout {
  type?: unknown
  scope?: unknown
  selected_nodes?: unknown
}

export interface KittyDesktopLlmModelUpdateFanout {
  type?: unknown
  scope?: unknown
  selected_llm_model?: unknown
}

export interface KittyDesktopVoiceCommandFanout {
  type?: unknown
  scope?: unknown
  action?: unknown
  detail?: unknown
}

export interface KittyDesktopVoicePhaseUpdateFanout {
  type?: unknown
  scope?: unknown
  phase?: unknown
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
export function createKittyDesktopWakeStream(options: KittyDesktopWakeStreamOptions): () => void {
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
    traceKittyWorkflow('hub', 'sse_reconnect', `retry in ${delayMs}ms`)
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
      const reconnected = retryCount > 0
      retryCount = 0
      traceKittyWorkflow('hub', 'sse_connect', reconnected ? 'reconnected' : 'connected')
      options.onOpen?.()
    }
    eventSource.onmessage = (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(String(event.data)) as unknown
        if (typeof parsed === 'object' && parsed !== null) {
          const row = parsed as { type?: unknown }
          if (row.type === 'desktop_action_pending') {
            options.onDesktopActionPending?.()
            return
          }
          if (row.type === 'diagram_update') {
            options.onDiagramUpdate?.(parsed as KittyDesktopDiagramUpdateFanout)
            return
          }
          if (row.type === 'selection_update') {
            options.onSelectionUpdate?.(parsed as KittyDesktopSelectionUpdateFanout)
            return
          }
          if (row.type === 'llm_model_update') {
            options.onLlmModelUpdate?.(parsed as KittyDesktopLlmModelUpdateFanout)
            return
          }
          if (row.type === 'voice_command') {
            options.onVoiceCommand?.(parsed as KittyDesktopVoiceCommandFanout)
            return
          }
          if (row.type === 'voice_phase_update') {
            options.onVoicePhaseUpdate?.(parsed as KittyDesktopVoicePhaseUpdateFanout)
            return
          }
        }
        const payload = parseMobileActivePayload(parsed)
        if (payload != null) {
          traceKittyWorkflow(
            'hub',
            'mobile_active',
            payload.active === true ? 'active' : 'inactive'
          )
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
