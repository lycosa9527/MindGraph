/**
 * Report frontend errors to the backend error collection pipeline.
 */
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'

type FrontendLogLevel = 'debug' | 'info' | 'warn' | 'error'

const MAX_MESSAGE_LEN = 4500
const DEDUPE_MS = 5000
const recentHashes = new Map<string, number>()

function shouldSkipReporting(): boolean {
  if (!import.meta.env.PROD) {
    return true
  }
  return isMindgraphHeadlessExportSession()
}

function hashMessage(message: string): string {
  let hash = 0
  for (let i = 0; i < message.length; i += 1) {
    hash = (hash * 31 + message.charCodeAt(i)) | 0
  }
  return String(hash)
}

function dedupeKey(err: unknown, context?: { source?: string; info?: string }): string {
  const msg = err instanceof Error ? err.message : String(err)
  return `${context?.source ?? ''}|${context?.info ?? ''}|${msg}`
}

function shouldDedupe(err: unknown, context?: { source?: string; info?: string }): boolean {
  const key = hashMessage(dedupeKey(err, context))
  const now = Date.now()
  const last = recentHashes.get(key)
  if (last !== undefined && now - last < DEDUPE_MS) {
    return true
  }
  recentHashes.set(key, now)
  if (recentHashes.size > 100) {
    const cutoff = now - DEDUPE_MS
    for (const [entryKey, entryTime] of recentHashes.entries()) {
      if (entryTime < cutoff) {
        recentHashes.delete(entryKey)
      }
    }
  }
  return false
}

function formatError(err: unknown, context?: { source?: string; info?: string }): string {
  const parts: string[] = []
  if (context?.source) {
    parts.push(`source=${context.source}`)
  }
  if (context?.info) {
    parts.push(`info=${context.info}`)
  }
  if (typeof window !== 'undefined') {
    parts.push(`path=${window.location.pathname}`)
  }
  if (err instanceof Error) {
    parts.push(`${err.name}: ${err.message}`)
    if (err.stack) {
      parts.push(err.stack)
    }
  } else {
    parts.push(String(err))
  }
  const message = parts.join('\n')
  if (message.length <= MAX_MESSAGE_LEN) {
    return message
  }
  return `${message.slice(0, MAX_MESSAGE_LEN)}\n... [truncated]`
}

export function reportFrontendLog(
  level: FrontendLogLevel,
  message: string,
  source?: string
): void {
  if (shouldSkipReporting()) {
    return
  }
  const body = {
    level,
    message: message.slice(0, MAX_MESSAGE_LEN),
    source,
  }
  void fetch('/api/frontend_log', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).catch(() => undefined)
}

export function reportFrontendError(
  err: unknown,
  context?: { source?: string; info?: string }
): void {
  if (shouldSkipReporting()) {
    return
  }
  const message = formatError(err, context)
  if (shouldDedupe(err, context)) {
    return
  }
  reportFrontendLog('error', message, context?.source)
}

/** Test-only reset for dedupe state. */
export function resetFrontendLogDedupeForTests(): void {
  recentHashes.clear()
}

/** Test-only gate override helpers. */
export function shouldSkipFrontendReportingForTests(): boolean {
  return shouldSkipReporting()
}
