/**
 * Maite API base helpers and SSE consumer.
 */
import { apiRequest } from '@/utils/apiClient'

import type { MaiteMentorStreamCallbacks } from '@/types/maite'

export const MAITE_API_PREFIX = '/api/maite'

export async function maiteRequestJson<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const endpoint = path.startsWith('/api/') ? path : `${MAITE_API_PREFIX}${path}`
  const response = await apiRequest(endpoint, options)
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : response.statusText || 'Request failed'
    throw new Error(detail)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

function readCsrfTokenFromCookie(): string | null {
  if (typeof document === 'undefined') {
    return null
  }
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

export async function consumeMaiteSseStream(
  endpoint: string,
  body: unknown,
  callbacks: MaiteMentorStreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const csrfToken = readCsrfTokenFromCookie()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }

  const response = await fetch(endpoint, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    credentials: 'same-origin',
    signal,
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const message =
      payload && typeof payload === 'object' && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : `HTTP ${response.status}`
    callbacks.onError?.(message)
    return
  }

  const reader = response.body?.getReader()
  if (!reader) {
    callbacks.onError?.('No response body')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = 'status'

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      if (buffer.trim()) {
        processMaiteSseChunk(buffer, callbacks, (event) => {
          currentEvent = event
        })
      }
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() || ''

    for (const frame of frames) {
      if (!frame.trim()) {
        continue
      }
      currentEvent = processMaiteSseChunk(frame, callbacks, (event) => {
        currentEvent = event
      }) ?? currentEvent
    }
  }
}

/** Parse one SSE frame for unit tests and stream consumer. */
export function parseMaiteSseBlock(frame: string): {
  event: string
  data: Record<string, unknown> | null
} {
  let eventName = 'message'
  let dataLine = ''
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim() || 'message'
    } else if (line.startsWith('data:')) {
      dataLine = line.slice(5).trim()
    }
  }
  if (!dataLine) {
    return { event: eventName, data: null }
  }
  try {
    return { event: eventName, data: JSON.parse(dataLine) as Record<string, unknown> }
  } catch {
    return { event: eventName, data: null }
  }
}

function processMaiteSseChunk(
  frame: string,
  callbacks: MaiteMentorStreamCallbacks,
  setEvent: (event: string) => void
): string | undefined {
  let eventName = 'status'
  let dataLine = ''

  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
      setEvent(eventName)
    } else if (line.startsWith('data:')) {
      dataLine = line.slice(5).trim()
    }
  }

  if (!dataLine) {
    return eventName
  }

  let parsed: Record<string, unknown> = {}
  try {
    parsed = JSON.parse(dataLine) as Record<string, unknown>
  } catch {
    callbacks.onError?.('Failed to parse stream payload')
    return eventName
  }

  switch (eventName) {
    case 'status':
      callbacks.onStatus?.(String(parsed.status ?? parsed.message ?? ''))
      break
    case 'preview':
      callbacks.onPreview?.(String(parsed.text ?? parsed.preview ?? ''))
      break
    case 'complete':
      callbacks.onComplete?.(parsed.payload ?? parsed)
      break
    case 'error':
      callbacks.onError?.(String(parsed.message ?? 'Stream error'))
      break
    default:
      callbacks.onStatus?.(eventName)
      break
  }

  return eventName
}
