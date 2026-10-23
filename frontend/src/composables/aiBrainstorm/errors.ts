/** Shared abort/stream error helpers for AI brainstorm SSE. */

export function isAbortError(err: unknown): boolean {
  if (err == null) return false
  if (typeof err === 'object' && 'name' in err && (err as { name: string }).name === 'AbortError') {
    return true
  }
  if (err instanceof Error) {
    if (err.name === 'AbortError') return true
    const msg = err.message.toLowerCase()
    return (
      msg.includes('aborted') ||
      msg.includes('bodystream') ||
      msg.includes('the user aborted a request')
    )
  }
  return false
}
