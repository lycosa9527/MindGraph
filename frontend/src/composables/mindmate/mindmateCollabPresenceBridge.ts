/**
 * Shared org presence for MindMate collab.
 *
 * A snapshot is the full set of people online at that moment. Anyone it
 * leaves out is offline, except a presence event that arrived in the few
 * seconds before the snapshot (that event is newer than the snapshot's
 * contents). An offline event records when they were last seen.
 */
import { ref } from 'vue'

import { useAuthStore } from '@/stores/auth'
import { buildWorkshopCacheScope } from '@/utils/workshopChatLocalCache'
import {
  loadLastSeenOnlineFromStorage,
  saveLastSeenOnlineToStorage,
} from '@/utils/workshopContactLastSeenStorage'

/** An active event this recent beat the snapshot that was already in flight. */
const SNAPSHOT_RACE_GRACE_MS = 5_000

const onlineUserIds = ref<Set<number>>(new Set())
const lastSeenOnlineAtByUserId = ref<Record<number, number>>({})
const presenceReady = ref(false)
const lastActiveAtMs = new Map<number, number>()

function persistLastSeen(): void {
  try {
    const auth = useAuthStore()
    const userId = auth.user?.id != null ? String(auth.user.id) : undefined
    const scope = buildWorkshopCacheScope(userId, null, auth.user?.schoolId)
    if (!scope) {
      return
    }
    saveLastSeenOnlineToStorage(scope, lastSeenOnlineAtByUserId.value)
  } catch {
    // Tests and early boot have no Pinia session. The in-memory map still updates.
  }
}

function hydrateLastSeen(): void {
  try {
    const auth = useAuthStore()
    const userId = auth.user?.id != null ? String(auth.user.id) : undefined
    const scope = buildWorkshopCacheScope(userId, null, auth.user?.schoolId)
    lastSeenOnlineAtByUserId.value = scope ? loadLastSeenOnlineFromStorage(scope) : {}
  } catch {
    lastSeenOnlineAtByUserId.value = {}
  }
}

function stampLastSeen(userId: number, now: number): void {
  lastSeenOnlineAtByUserId.value = {
    ...lastSeenOnlineAtByUserId.value,
    [userId]: now,
  }
}

function clearLastSeen(userId: number): boolean {
  if (lastSeenOnlineAtByUserId.value[userId] === undefined) {
    return false
  }
  const rest = { ...lastSeenOnlineAtByUserId.value }
  delete rest[userId]
  lastSeenOnlineAtByUserId.value = rest
  return true
}

export function useMindmateCollabPresenceBridge() {
  function updatePresence(userId: number, status: string, now = Date.now()): void {
    if (!Number.isFinite(userId) || userId <= 0) {
      return
    }
    const next = new Set(onlineUserIds.value)
    if (status === 'offline') {
      lastActiveAtMs.delete(userId)
      if (next.has(userId)) {
        stampLastSeen(userId, now)
        persistLastSeen()
      }
      next.delete(userId)
    } else {
      lastActiveAtMs.set(userId, now)
      next.add(userId)
      if (clearLastSeen(userId)) {
        persistLastSeen()
      }
    }
    onlineUserIds.value = next
  }

  function applyPresenceSnapshot(ids: number[], selfUserId?: number, now = Date.now()): void {
    const next = new Set<number>()
    for (const uid of ids) {
      if (Number.isFinite(uid) && uid > 0) {
        next.add(uid)
      }
    }
    if (selfUserId && selfUserId > 0) {
      next.add(selfUserId)
    }
    let seenChanged = false
    for (const uid of onlineUserIds.value) {
      if (next.has(uid)) {
        continue
      }
      const activeAt = lastActiveAtMs.get(uid) ?? 0
      const age = now - activeAt
      if (age >= 0 && age < SNAPSHOT_RACE_GRACE_MS) {
        next.add(uid)
        continue
      }
      lastActiveAtMs.delete(uid)
      stampLastSeen(uid, now)
      seenChanged = true
    }
    for (const uid of next) {
      if (clearLastSeen(uid)) {
        seenChanged = true
      }
    }
    if (seenChanged) {
      persistLastSeen()
    }
    onlineUserIds.value = next
    presenceReady.value = true
  }

  return {
    onlineUserIds,
    lastSeenOnlineAtByUserId,
    presenceReady,
    applyPresenceSnapshot,
    updatePresence,
    hydrateLastSeen,
  }
}
