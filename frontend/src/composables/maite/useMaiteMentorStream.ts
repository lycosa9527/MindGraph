/**
 * Maite mentor SSE stream runner — listens for stop and emits bus events.
 */
import { onScopeDispose, ref } from 'vue'

import { decomposeStream, followUpStream } from '@/api/maite/mentor'
import { eventBus, useEventBus } from '@/composables/core/useEventBus'

import type { MaiteDecomposeTables, MaiteMentorFollowUpResult } from '@/types/maite'

/**
 * Abort only if the SSE connection goes silent (no status/preview/complete).
 * TTFT for plus can exceed 45s when json_object was used; keep a generous
 * silence window as a safety net for truly hung connections.
 */
const STALL_TIMEOUT_MS = 120000

export function useMaiteMentorStream(owner = 'MaiteMentorStream') {
  const bus = useEventBus(owner)
  const abortController = ref<AbortController | null>(null)
  const isStreaming = ref(false)
  const streamStatus = ref('')
  const streamPreview = ref('')

  bus.on('maite:mentor_stream_stop', () => {
    stopStream()
  })

  function stopStream(): void {
    abortController.value?.abort()
    abortController.value = null
    isStreaming.value = false
    streamStatus.value = ''
  }

  function normalizeStatus(status: string): string {
    if (!status || status === 'streaming' || status === 'starting') {
      return ''
    }
    // Pass through phase labels used by MaiteStreamStatus.
    return status
  }

  function applyPreview(text: string): void {
    const current = streamPreview.value
    // Backend sends cumulative buffer; tolerate delta chunks from older servers.
    if (!current || text.startsWith(current)) {
      streamPreview.value = text
      return
    }
    if (current.startsWith(text)) {
      return
    }
    streamPreview.value = current + text
  }

  async function runDecomposeStream(question: string): Promise<MaiteDecomposeTables | null> {
    stopStream()
    const controller = new AbortController()
    abortController.value = controller
    isStreaming.value = true
    streamPreview.value = ''
    streamStatus.value = ''

    let result: MaiteDecomposeTables | null = null
    let sawError = false
    let stallTimer: number | null = null

    const armStallTimer = (): void => {
      if (stallTimer != null) {
        window.clearTimeout(stallTimer)
      }
      stallTimer = window.setTimeout(() => {
        if (!controller.signal.aborted) {
          controller.abort()
        }
      }, STALL_TIMEOUT_MS)
    }

    armStallTimer()

    try {
      await decomposeStream(
        { question },
        {
          onStatus: (status) => {
            armStallTimer()
            streamStatus.value = normalizeStatus(status)
            eventBus.emit('maite:mentor_stream_status', { status })
          },
          onPreview: (text) => {
            armStallTimer()
            applyPreview(text)
            eventBus.emit('maite:mentor_stream_preview', {
              text: streamPreview.value,
            })
          },
          onComplete: (payload) => {
            armStallTimer()
            result = payload as MaiteDecomposeTables
            eventBus.emit('maite:mentor_stream_complete', { payload })
          },
          onError: (message) => {
            sawError = true
            eventBus.emit('maite:mentor_stream_error', { message })
            eventBus.emit('maite:error', { message, source: 'mentor_decompose' })
          },
        },
        controller.signal
      )
      if (!result && !sawError && !controller.signal.aborted) {
        eventBus.emit('maite:error', {
          message: 'decompose_failed',
          source: 'mentor_decompose',
        })
      }
      return result
    } catch (error: unknown) {
      if (error instanceof Error && error.name !== 'AbortError') {
        eventBus.emit('maite:mentor_stream_error', { message: error.message })
        eventBus.emit('maite:error', {
          message: error.message || 'decompose_failed',
          source: 'mentor_decompose',
        })
      }
      return null
    } finally {
      if (stallTimer != null) {
        window.clearTimeout(stallTimer)
      }
      isStreaming.value = false
      abortController.value = null
    }
  }

  async function runFollowUpStream(input: {
    question: string
    reply: string
    history?: Record<string, unknown>[]
    decomposition?: MaiteDecomposeTables
  }): Promise<MaiteMentorFollowUpResult | null> {
    stopStream()
    const controller = new AbortController()
    abortController.value = controller
    isStreaming.value = true
    streamPreview.value = ''
    streamStatus.value = ''

    let result: MaiteMentorFollowUpResult | null = null
    let sawError = false
    let stallTimer: number | null = null

    const armStallTimer = (): void => {
      if (stallTimer != null) {
        window.clearTimeout(stallTimer)
      }
      stallTimer = window.setTimeout(() => {
        if (!controller.signal.aborted) {
          controller.abort()
        }
      }, STALL_TIMEOUT_MS)
    }

    armStallTimer()

    try {
      await followUpStream(
        input,
        {
          onStatus: (status) => {
            armStallTimer()
            streamStatus.value = normalizeStatus(status)
            eventBus.emit('maite:mentor_stream_status', { status })
          },
          onPreview: (text) => {
            armStallTimer()
            applyPreview(text)
            eventBus.emit('maite:mentor_stream_preview', {
              text: streamPreview.value,
            })
          },
          onComplete: (payload) => {
            armStallTimer()
            result = payload as MaiteMentorFollowUpResult
            eventBus.emit('maite:mentor_stream_complete', { payload })
          },
          onError: (message) => {
            sawError = true
            eventBus.emit('maite:mentor_stream_error', { message })
            eventBus.emit('maite:error', { message, source: 'mentor_follow_up' })
          },
        },
        controller.signal
      )
      if (!result && !sawError && !controller.signal.aborted) {
        eventBus.emit('maite:error', {
          message: 'follow_up_failed',
          source: 'mentor_follow_up',
        })
      }
      return result
    } catch (error: unknown) {
      if (error instanceof Error && error.name !== 'AbortError') {
        eventBus.emit('maite:mentor_stream_error', { message: error.message })
        eventBus.emit('maite:error', {
          message: error.message || 'follow_up_failed',
          source: 'mentor_follow_up',
        })
      }
      return null
    } finally {
      if (stallTimer != null) {
        window.clearTimeout(stallTimer)
      }
      isStreaming.value = false
      abortController.value = null
    }
  }

  onScopeDispose(() => {
    stopStream()
  })

  return {
    isStreaming,
    streamStatus,
    streamPreview,
    runDecomposeStream,
    runFollowUpStream,
    stopStream,
  }
}
