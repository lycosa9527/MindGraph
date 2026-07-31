/**
 * Maite mentor SSE stream runner — listens for stop and emits bus events.
 */
import { onScopeDispose, ref } from 'vue'

import { decomposeStream, followUpStream } from '@/api/maite/mentor'
import { eventBus, useEventBus } from '@/composables/core/useEventBus'

import type { MaiteDecomposeTables, MaiteMentorFollowUpResult } from '@/types/maite'

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

  async function runDecomposeStream(question: string): Promise<MaiteDecomposeTables | null> {
    stopStream()
    const controller = new AbortController()
    abortController.value = controller
    isStreaming.value = true
    streamPreview.value = ''
    streamStatus.value = 'starting'

    let result: MaiteDecomposeTables | null = null

    try {
      await decomposeStream(
        { question },
        {
          onStatus: (status) => {
            streamStatus.value = status
            eventBus.emit('maite:mentor_stream_status', { status })
          },
          onPreview: (text) => {
            streamPreview.value = text
            eventBus.emit('maite:mentor_stream_preview', { text })
          },
          onComplete: (payload) => {
            result = payload as MaiteDecomposeTables
            eventBus.emit('maite:mentor_stream_complete', { payload })
          },
          onError: (message) => {
            eventBus.emit('maite:mentor_stream_error', { message })
            eventBus.emit('maite:error', { message, source: 'mentor_decompose' })
          },
        },
        controller.signal
      )
      return result
    } catch (error: unknown) {
      if (error instanceof Error && error.name !== 'AbortError') {
        eventBus.emit('maite:mentor_stream_error', { message: error.message })
      }
      return null
    } finally {
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
    streamStatus.value = 'starting'

    let result: MaiteMentorFollowUpResult | null = null

    try {
      await followUpStream(
        input,
        {
          onStatus: (status) => {
            streamStatus.value = status
            eventBus.emit('maite:mentor_stream_status', { status })
          },
          onPreview: (text) => {
            streamPreview.value = text
            eventBus.emit('maite:mentor_stream_preview', { text })
          },
          onComplete: (payload) => {
            result = payload as MaiteMentorFollowUpResult
            eventBus.emit('maite:mentor_stream_complete', { payload })
          },
          onError: (message) => {
            eventBus.emit('maite:mentor_stream_error', { message })
            eventBus.emit('maite:error', { message, source: 'mentor_follow_up' })
          },
        },
        controller.signal
      )
      return result
    } catch (error: unknown) {
      if (error instanceof Error && error.name !== 'AbortError') {
        eventBus.emit('maite:mentor_stream_error', { message: error.message })
      }
      return null
    } finally {
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
