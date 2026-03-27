/** Shared abort/stream error helpers for node palette SSE. */

export function isAbortError(err: unknown): boolean {
  if (err instanceof Error) {
    if (err.name === 'AbortError') return true
    const msg = err.message.toLowerCase()
    return msg.includes('aborted') || msg.includes('bodystream')
  }
  return false
}
