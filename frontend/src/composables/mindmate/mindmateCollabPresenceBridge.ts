/**
 * Shared org presence state for MindMate collab (notify WS + member panel).
 */
import { ref } from 'vue'

const onlineUserIds = ref<Set<number>>(new Set())

export function useMindmateCollabPresenceBridge() {
  function applyPresenceSnapshot(ids: number[], selfUserId?: number): void {
    const next = new Set<number>()
    for (const uid of ids) {
      if (Number.isFinite(uid)) {
        next.add(uid)
      }
    }
    if (selfUserId) {
      next.add(selfUserId)
    }
    onlineUserIds.value = next
  }

  function updatePresence(userId: number, status: string): void {
    const next = new Set(onlineUserIds.value)
    if (status === 'offline') {
      next.delete(userId)
    } else {
      next.add(userId)
    }
    onlineUserIds.value = next
  }

  return {
    onlineUserIds,
    applyPresenceSnapshot,
    updatePresence,
  }
}

export function clearMindmateCollabPresenceSnapshot(): void {
  onlineUserIds.value = new Set()
}
