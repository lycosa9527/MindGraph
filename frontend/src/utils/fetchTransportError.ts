/** Browser fetch failures: the request never completed, or it was aborted. */
export function isFetchTransportError(err: unknown): boolean {
  if (
    typeof err === 'object' &&
    err !== null &&
    'name' in err &&
    (err as { name?: unknown }).name === 'AbortError'
  ) {
    return true
  }
  if (!(err instanceof Error)) return false
  const message = err.message
  return (
    message === 'Failed to fetch' || message === 'Load failed' || message.startsWith('NetworkError')
  )
}
