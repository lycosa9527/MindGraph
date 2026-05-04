/**
 * Participant join/leave notification coalescing and room idle UI helpers.
 */
import { ref } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import type { WorkshopUpdate } from '@/composables/workshop/useWorkshopTypes'

import { netPresenceAfterCancellingPairs } from './useWorkshopReconnect'

export function useWorkshopPresence() {
  const notify = useNotifications()
  const { t } = useLanguage()

  let presenceJoinedBuffer: string[] = []
  let presenceLeftBuffer: string[] = []
  let presenceCoalesceTimer: ReturnType<typeof setTimeout> | null = null

  function flushPresenceNotifications(): void {
    presenceCoalesceTimer = null
    const joinedRaw = presenceJoinedBuffer.splice(0)
    const leftRaw = presenceLeftBuffer.splice(0)
    const { joined, left } = netPresenceAfterCancellingPairs(joinedRaw, leftRaw)
    if (joined.length === 1) {
      notify.info(t('workshopCanvas.userJoined', { username: joined[0] }))
    } else if (joined.length > 1) {
      notify.info(t('workshopCanvas.usersJoined', { count: joined.length }))
    }
    if (left.length === 1) {
      notify.info(t('workshopCanvas.userLeft', { username: left[0] }))
    } else if (left.length > 1) {
      notify.info(t('workshopCanvas.usersLeft', { count: left.length }))
    }
  }

  function schedulePresenceNotification(type: 'joined' | 'left', username: string): void {
    if (type === 'joined') {
      presenceJoinedBuffer.push(username)
    } else {
      presenceLeftBuffer.push(username)
    }
    if (!presenceCoalesceTimer) {
      presenceCoalesceTimer = setTimeout(flushPresenceNotifications, 500)
    }
  }

  function clearPresenceCoalescer(): void {
    if (presenceCoalesceTimer) {
      clearTimeout(presenceCoalesceTimer)
      presenceCoalesceTimer = null
    }
    presenceJoinedBuffer = []
    presenceLeftBuffer = []
  }

  const roomIdleSecondsRemaining = ref<number | null>(null)

  let roomIdleDeadlineUnixInternal: number | null = null
  let roomIdleTickInterval: ReturnType<typeof setInterval> | null = null

  function stopRoomIdleCountdownTick(): void {
    if (roomIdleTickInterval) {
      clearInterval(roomIdleTickInterval)
      roomIdleTickInterval = null
    }
  }

  function syncRoomIdleSecondsFromDeadline(): void {
    if (roomIdleDeadlineUnixInternal == null) {
      roomIdleSecondsRemaining.value = null
      return
    }
    roomIdleSecondsRemaining.value = Math.max(
      0,
      roomIdleDeadlineUnixInternal - Math.floor(Date.now() / 1000)
    )
  }

  function clearRoomIdleCountdownUi(): void {
    roomIdleDeadlineUnixInternal = null
    roomIdleSecondsRemaining.value = null
    stopRoomIdleCountdownTick()
  }

  function applyRoomIdleWarningFromServer(payload: WorkshopUpdate): void {
    const fallbackGrace =
      typeof payload.grace_seconds_remaining === 'number'
        ? Math.max(1, payload.grace_seconds_remaining)
        : 60
    let deadlineUnix: number
    if (typeof payload.idle_deadline_unix === 'number') {
      deadlineUnix = payload.idle_deadline_unix
    } else {
      deadlineUnix = Math.floor(Date.now() / 1000) + fallbackGrace
    }

    clearRoomIdleCountdownUi()
    roomIdleDeadlineUnixInternal = deadlineUnix
    syncRoomIdleSecondsFromDeadline()
    notify.warning(t('workshopCanvas.roomIdleWarningToast'))

    stopRoomIdleCountdownTick()
    roomIdleTickInterval = setInterval(() => syncRoomIdleSecondsFromDeadline(), 1000)
  }

  return {
    roomIdleSecondsRemaining,
    schedulePresenceNotification,
    clearPresenceCoalescer,
    clearRoomIdleCountdownUi,
    applyRoomIdleWarningFromServer,
  }
}
