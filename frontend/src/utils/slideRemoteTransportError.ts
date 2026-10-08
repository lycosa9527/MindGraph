/** Dropped-network failures from the slide-remote command drain. */
export function isSlideRemoteTransportError(err: unknown): boolean {
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
