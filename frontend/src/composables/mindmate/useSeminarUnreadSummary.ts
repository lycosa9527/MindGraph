/**
 * Live MindMate seminar unread counts for sidebar history and MindMate nav.
 * Backed by GET /api/mindmate/seminar/unread-summary (same as desktop pet).
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { authFetch } from '@/utils/api'

export interface SeminarUnreadRoom {
  session_id: string
  code: string
  title: string
  unread_count: number
  latest_message_id: number
}

const POLL_MS = 45_000

const totalUnread = ref(0)
const roomsBySessionId = ref<Record<string, number>>({})
let pollTimer: ReturnType<typeof setInterval> | null = null
let subscribers = 0
let fetchInFlight = false

async function fetchUnreadSummary(): Promise<void> {
  if (fetchInFlight) {
    return
  }
  fetchInFlight = true
  try {
    const response = await authFetch('/api/mindmate/seminar/unread-summary')
    if (!response.ok) {
      return
    }
    const data = (await response.json()) as {
      unread_count?: number
      rooms?: SeminarUnreadRoom[]
    }
    const next: Record<string, number> = {}
    for (const room of data.rooms || []) {
      const id = String(room.session_id || '').trim()
      const count = Number(room.unread_count) || 0
      if (id && count > 0) {
        next[id] = count
      }
    }
    roomsBySessionId.value = next
    totalUnread.value = Number(data.unread_count) || 0
  } catch {
    // Keep last known counts on transient errors.
  } finally {
    fetchInFlight = false
  }
}

function onVisibility(): void {
  if (document.visibilityState === 'visible') {
    void fetchUnreadSummary()
  }
}

function ensurePolling(): void {
  if (pollTimer != null) {
    return
  }
  pollTimer = setInterval(() => {
    if (document.visibilityState === 'visible') {
      void fetchUnreadSummary()
    }
  }, POLL_MS)
  document.addEventListener('visibilitychange', onVisibility)
}

function stopPollingIfIdle(): void {
  if (subscribers > 0) {
    return
  }
  if (pollTimer != null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  document.removeEventListener('visibilitychange', onVisibility)
}

/** Subscribe from sidebar history / nav; refreshes on mount and while subscribed. */
export function useSeminarUnreadSummary() {
  onMounted(() => {
    subscribers += 1
    ensurePolling()
    void fetchUnreadSummary()
  })
  onUnmounted(() => {
    subscribers = Math.max(0, subscribers - 1)
    stopPollingIfIdle()
  })

  return {
    seminarUnreadTotal: computed(() => totalUnread.value),
    seminarUnreadBySessionId: computed(() => roomsBySessionId.value),
    refreshSeminarUnread: fetchUnreadSummary,
    unreadForSession(sessionId: string): number {
      return roomsBySessionId.value[sessionId] || 0
    },
  }
}

/** One-shot refresh for callers that already hold a subscription elsewhere. */
export function refreshSeminarUnreadSummary(): Promise<void> {
  return fetchUnreadSummary()
}
