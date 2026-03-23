/**
 * Persist per-user "last seen online" timestamps for workshop contact grouping.
 * Scoped by user + org (same keys as workshop chat cache).
 */
import type { WorkshopCacheScope } from '@/utils/workshopChatLocalCache'

const PREFIX = 'mg_ws_v1_lso'

/** Drop entries older than this from storage and from "recently online" UI. */
export const LAST_SEEN_ONLINE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000

function storageKey(scope: WorkshopCacheScope): string {
  return `${PREFIX}_${scope.userId}_${scope.orgKey}`
}

function pruneByAge(data: Record<number, number>, maxAgeMs: number): Record<number, number> {
  const now = Date.now()
  const out: Record<number, number> = {}
  for (const [key, ts] of Object.entries(data)) {
    const uid = Number(key)
    if (Number.isNaN(uid) || typeof ts !== 'number') {
      continue
    }
    const age = now - ts
    if (age >= 0 && age <= maxAgeMs) {
      out[uid] = ts
    }
  }
  return out
}

export function loadLastSeenOnlineFromStorage(scope: WorkshopCacheScope): Record<number, number> {
  if (typeof localStorage === 'undefined') {
    return {}
  }
  try {
    const raw = localStorage.getItem(storageKey(scope))
    if (!raw) {
      return {}
    }
    const parsed = JSON.parse(raw) as Record<string, unknown>
    if (typeof parsed !== 'object' || parsed === null) {
      return {}
    }
    const numeric: Record<number, number> = {}
    for (const [k, v] of Object.entries(parsed)) {
      const uid = Number(k)
      if (Number.isNaN(uid) || typeof v !== 'number') {
        continue
      }
      numeric[uid] = v
    }
    return pruneByAge(numeric, LAST_SEEN_ONLINE_MAX_AGE_MS)
  } catch {
    return {}
  }
}

export function saveLastSeenOnlineToStorage(
  scope: WorkshopCacheScope,
  data: Record<number, number>,
): void {
  if (typeof localStorage === 'undefined') {
    return
  }
  try {
    const pruned = pruneByAge(data, LAST_SEEN_ONLINE_MAX_AGE_MS)
    localStorage.setItem(storageKey(scope), JSON.stringify(pruned))
  } catch {
    // Quota or private mode — ignore
  }
}
