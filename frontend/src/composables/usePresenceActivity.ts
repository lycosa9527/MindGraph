/**
 * Presence Activity Composable
 *
 * Tracks user activity (mouse, keyboard, touch, focus) and reports
 * idle/active status via a callback.  Mirrors Zulip's activity.ts:
 *   - Active on focus / keydown / mousedown / mousemove / touchstart / wheel
 *   - Idle after 5 minutes of no activity
 */
import { onMounted, onUnmounted, ref } from 'vue'

const IDLE_TIMEOUT_MS = 5 * 60 * 1000

export function usePresenceActivity(onStatusChange: (status: 'active' | 'idle') => void) {
  const clientIsActive = ref(document.hasFocus())
  let idleTimer: ReturnType<typeof setTimeout> | null = null

  function scheduleIdle(): void {
    if (idleTimer) clearTimeout(idleTimer)
    idleTimer = setTimeout(() => {
      if (clientIsActive.value) {
        clientIsActive.value = false
        onStatusChange('idle')
      }
    }, IDLE_TIMEOUT_MS)
  }

  function markActive(): void {
    if (!clientIsActive.value) {
      clientIsActive.value = true
      onStatusChange('active')
    }
    scheduleIdle()
  }

  const ACTIVITY_EVENTS: Array<keyof WindowEventMap> = [
    'focus',
    'keydown',
    'mousedown',
    'mousemove',
    'touchstart',
    'wheel',
  ]

  onMounted(() => {
    for (const evt of ACTIVITY_EVENTS) {
      window.addEventListener(evt, markActive, { passive: true })
    }
    scheduleIdle()
  })

  onUnmounted(() => {
    for (const evt of ACTIVITY_EVENTS) {
      window.removeEventListener(evt, markActive)
    }
    if (idleTimer) clearTimeout(idleTimer)
  })

  return { clientIsActive }
}
