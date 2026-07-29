/**
 * SSE listener for Showcase teaching-design cover_ready / cover_fail.
 * Event-based — no polling. Hard-stops when the server sends a terminal
 * event or the connection ends without one.
 */

export const showcaseCoverStreamUrl = (postId: string): string =>
  `/api/showcase/posts/${encodeURIComponent(postId)}/cover-stream`

export type ShowcaseCoverReadyEvent = {
  type: 'cover_ready'
  postId: string
  thumbnailUrl?: string | null
}

export type ShowcaseCoverFailEvent = {
  type: 'cover_fail'
  postId: string
  reason?: string | null
}

export type ShowcaseCoverStreamOptions = {
  onReady: (event: ShowcaseCoverReadyEvent) => void
  onFail: (event: ShowcaseCoverFailEvent) => void
  onOpen?: () => void
  onError?: (event: Event) => void
}

function parseCoverPayload(raw: unknown): ShowcaseCoverReadyEvent | ShowcaseCoverFailEvent | null {
  if (typeof raw !== 'object' || raw === null) return null
  const row = raw as Record<string, unknown>
  const postId = typeof row.post_id === 'string' ? row.post_id : ''
  if (!postId) return null
  if (row.type === 'cover_ready') {
    return {
      type: 'cover_ready',
      postId,
      thumbnailUrl: typeof row.thumbnail_url === 'string' ? row.thumbnail_url : null,
    }
  }
  if (row.type === 'cover_fail') {
    return {
      type: 'cover_fail',
      postId,
      reason: typeof row.reason === 'string' ? row.reason : null,
    }
  }
  return null
}

/**
 * Opens EventSource for one post cover job. Returns teardown.
 * Does not auto-reconnect after a terminal event or explicit close.
 */
export function createShowcaseCoverStream(
  postId: string,
  options: ShowcaseCoverStreamOptions,
): () => void {
  if (typeof EventSource === 'undefined' || !postId) {
    return () => undefined
  }

  let closed = false
  let terminal = false
  let eventSource: EventSource | null = null

  function cleanup(): void {
    if (closed) return
    closed = true
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
  }

  function handleTerminal(payload: ShowcaseCoverReadyEvent | ShowcaseCoverFailEvent): void {
    if (terminal) return
    terminal = true
    if (payload.type === 'cover_ready') {
      options.onReady(payload)
    } else {
      options.onFail(payload)
    }
    cleanup()
  }

  eventSource = new EventSource(showcaseCoverStreamUrl(postId))
  eventSource.onopen = () => {
    options.onOpen?.()
  }
  eventSource.onmessage = (message) => {
    if (closed || terminal) return
    let parsed: unknown
    try {
      parsed = JSON.parse(message.data) as unknown
    } catch {
      return
    }
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      (parsed as { type?: unknown }).type === 'heartbeat'
    ) {
      return
    }
    const event = parseCoverPayload(parsed)
    if (event) handleTerminal(event)
  }
  eventSource.onerror = (event) => {
    options.onError?.(event)
    // EventSource reconnects by default; if the server closed after a
    // terminal frame we already cleaned up. Otherwise treat drop as fail.
    if (!closed && !terminal && eventSource?.readyState === EventSource.CLOSED) {
      handleTerminal({ type: 'cover_fail', postId, reason: 'stream_closed' })
    }
  }

  return cleanup
}
