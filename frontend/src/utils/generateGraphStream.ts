/**
 * SSE consumer for POST /api/generate_graph/stream (auto-complete phase colors).
 */
import { eventBus } from '@/composables/core/useEventBus'

export type GenerateGraphStreamPhase =
  | 'accepted'
  | 'detecting'
  | 'requirements'
  | 'progress'
  | 'waiting'
  | 'streaming'

export interface GenerateGraphCompletePayload {
  success?: boolean
  spec?: Record<string, unknown>
  diagram_type?: string
  language?: string
  error?: string
  error_type?: string
  show_guidance?: boolean
  warning?: string
  llm_model?: string
  request_id?: string
  is_learning_sheet?: boolean
  hidden_node_percentage?: number
}

export interface GenerateGraphProgressMetadata {
  topic?: string
  diagram_type?: string
}

export interface GenerateGraphStreamCallbacks {
  onPhase?: (phase: GenerateGraphStreamPhase) => void
  onProgress?: (metadata: GenerateGraphProgressMetadata) => void
  onComplete?: (payload: GenerateGraphCompletePayload) => void
  onError?: (message: string, errorType?: string) => void
}

function parseSseDataLine(line: string): Record<string, unknown> | null {
  if (!line.startsWith('data: ')) {
    return null
  }
  try {
    return JSON.parse(line.slice(6)) as Record<string, unknown>
  } catch {
    return null
  }
}

function isStreamPhase(value: unknown): value is GenerateGraphStreamPhase {
  return (
    value === 'accepted' ||
    value === 'detecting' ||
    value === 'requirements' ||
    value === 'progress' ||
    value === 'waiting' ||
    value === 'streaming'
  )
}

/**
 * Consume an SSE response from generate_graph/stream.
 * Returns usedStream=false when Content-Type is not event-stream (caller should JSON-fallback).
 */
export async function consumeGenerateGraphStream(
  response: Response,
  callbacks: GenerateGraphStreamCallbacks,
  signal?: AbortSignal
): Promise<{ usedStream: boolean; payload?: GenerateGraphCompletePayload }> {
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('text/event-stream')) {
    return { usedStream: false }
  }

  const reader = response.body?.getReader()
  if (!reader) {
    callbacks.onError?.('No response body')
    return { usedStream: true }
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let completePayload: GenerateGraphCompletePayload | undefined

  try {
    while (true) {
      if (signal?.aborted) {
        break
      }
      const chunk = await reader.read()
      const { done, value } = chunk
      if (done) {
        break
      }
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        const data = parseSseDataLine(line)
        if (!data) {
          continue
        }
        const event = data.event
        if (isStreamPhase(event)) {
          callbacks.onPhase?.(event)
          if (event === 'progress') {
            callbacks.onProgress?.({
              topic: typeof data.topic === 'string' ? data.topic : undefined,
              diagram_type:
                typeof data.diagram_type === 'string' ? data.diagram_type : undefined,
            })
          }
        } else if (event === 'complete') {
          completePayload = data as GenerateGraphCompletePayload
          callbacks.onComplete?.(completePayload)
        } else if (event === 'error') {
          const message =
            typeof data.message === 'string' ? data.message : 'Request failed'
          const errorType =
            typeof data.error_type === 'string' ? data.error_type : undefined
          if (errorType === 'thinking_coin_insufficient') {
            eventBus.emit('thinking_coins:insufficient', {})
          }
          callbacks.onError?.(message, errorType)
        }
      }
    }
  } finally {
    reader.releaseLock()
  }

  return { usedStream: true, payload: completePayload }
}
