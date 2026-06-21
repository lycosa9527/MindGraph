/**
 * Buffered SSE line reader for MindMate Dify streams (same pattern as generateGraphStream).
 */
export async function consumeSseDataLines(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onData: (payload: Record<string, unknown>) => boolean | void,
  signal?: AbortSignal | null
): Promise<void> {
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      if (signal?.aborted) {
        break
      }
      const { done, value } = await reader.read()
      if (done) {
        break
      }
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) {
          continue
        }
        try {
          const payload = JSON.parse(line.slice(6)) as Record<string, unknown>
          const stop = onData(payload)
          if (stop === false) {
            return
          }
        } catch {
          // Skip malformed JSON lines
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
