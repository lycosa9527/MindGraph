/**
 * Detect stale Vite chunk / CSS preload failures after deploy.
 */
export function isStaleChunkLoadError(err: unknown): boolean {
  const message = err instanceof Error ? err.message : String(err ?? '')
  if (!message) {
    return false
  }
  return (
    /Failed to fetch dynamically imported module/i.test(message) ||
    /error loading dynamically imported module/i.test(message) ||
    /Unable to preload CSS for/i.test(message) ||
    /Importing a module script failed/i.test(message) ||
    /Loading chunk [\w-]+ failed/i.test(message)
  )
}

const RELOAD_GUARD_KEY = 'mg_chunk_reload_at'
const RELOAD_COOLDOWN_MS = 15_000

/**
 * One-shot hard reload for stale assets. Returns true if a reload was scheduled.
 */
export function reloadForStaleChunk(err: unknown): boolean {
  if (typeof window === 'undefined' || !isStaleChunkLoadError(err)) {
    return false
  }
  try {
    const last = Number(sessionStorage.getItem(RELOAD_GUARD_KEY) ?? '0')
    const now = Date.now()
    if (Number.isFinite(last) && now - last < RELOAD_COOLDOWN_MS) {
      return false
    }
    sessionStorage.setItem(RELOAD_GUARD_KEY, String(now))
  } catch {
    /* sessionStorage may be unavailable */
  }
  window.location.reload()
  return true
}
