/**
 * NDJSON consumer for POST /api/canvas/translate_diagram_labels_stream.
 */

export type DiagramTranslateStreamItem = {
  event: 'item'
  item_id: string
  item_kind: 'node' | 'connection'
  translated_text: string
}

type StreamHandlers = {
  onStart?: (totalItems: number) => void
  onItem: (row: DiagramTranslateStreamItem) => void
  onDone?: () => void
  onError: (message: string) => void
}

function coerceItemPayload(raw: Record<string, unknown>): DiagramTranslateStreamItem | null {
  if (raw.event !== 'item') {
    return null
  }
  const itemId = raw.item_id
  const text = raw.translated_text
  if (typeof itemId !== 'string' || typeof text !== 'string') {
    return null
  }
  const kindRaw = raw.item_kind
  const itemKind = kindRaw === 'connection' ? 'connection' : 'node'
  return {
    event: 'item',
    item_id: itemId,
    item_kind: itemKind,
    translated_text: text,
  }
}

/**
 * Read newline-delimited JSON events until `done` or `error`.
 */
export async function consumeDiagramTranslateNdjsonStream(
  response: Response,
  handlers: StreamHandlers
): Promise<void> {
  if (!response.body) {
    handlers.onError('No response body')
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let sawDone = false

  const dispatchLine = (line: string): boolean => {
    const trimmed = line.trim()
    if (!trimmed) {
      return false
    }
    let msg: Record<string, unknown>
    try {
      msg = JSON.parse(trimmed) as Record<string, unknown>
    } catch {
      handlers.onError('Invalid translation stream')
      return true
    }
    const ev = msg.event
    if (ev === 'start') {
      const total = Number(msg.total_items ?? 0)
      handlers.onStart?.(Number.isFinite(total) ? total : 0)
    } else if (ev === 'item') {
      const row = coerceItemPayload(msg)
      if (!row || !row.translated_text.trim()) {
        handlers.onError('Invalid translation item')
        return true
      }
      handlers.onItem(row)
    } else if (ev === 'done') {
      sawDone = true
      handlers.onDone?.()
    } else if (ev === 'error') {
      const detail = msg.detail
      handlers.onError(typeof detail === 'string' ? detail : 'Translation failed')
      return true
    }
    return false
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n')
      buffer = parts.pop() ?? ''
      for (const part of parts) {
        const stop = dispatchLine(part)
        if (stop) {
          return
        }
      }
    }
    if (buffer.trim()) {
      dispatchLine(buffer)
    }
    if (!sawDone) {
      handlers.onError('Translation stream ended unexpectedly')
    }
  } catch (error) {
    console.error('Diagram translate stream read error:', error)
    handlers.onError('Translation failed')
  }
}
