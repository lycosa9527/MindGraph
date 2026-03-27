/**
 * Presence Activity Composable
 *
 * Emits `active` when the user shows activity (focus / keydown / mouse /
 * touch / wheel). Workshop chat presence treats “online” as WebSocket
 * connected; we do not emit a client-side idle tier after inactivity.
 */
import { onMounted, onUnmounted, ref } from 'vue'

export function usePresenceActivity(onStatusChange: (status: 'active') => void) {
  const clientIsActive = ref(document.hasFocus())

  function markActive(): void {
    if (!clientIsActive.value) {
      clientIsActive.value = true
      onStatusChange('active')
    }
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
  })

  onUnmounted(() => {
    for (const evt of ACTIVITY_EVENTS) {
      window.removeEventListener(evt, markActive)
    }
  })

  return { clientIsActive }
}
