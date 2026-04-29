import { ref, watch } from 'vue'

import { useUIStore } from '@/stores/ui'

/**
 * Single open flag for {@link CanvasVirtualKeyboardPanel}, shared by the main
 * toolbar “more apps” entry and the presentation side rail (Ctrl+6 / slot 6).
 */
export const canvasVirtualKeyboardOpen = ref(false)

let uiVersionWatchRegistered = false

export function toggleCanvasVirtualKeyboard(): void {
  canvasVirtualKeyboardOpen.value = !canvasVirtualKeyboardOpen.value
}

/**
 * When UI is not international, the virtual keyboard app is hidden; keep panel
 * state consistent. Idempotent so multiple {@link useCanvasToolbarApps} callers
 * register at most one watcher.
 */
export function ensureCanvasVirtualKeyboardUiVersionSync(): void {
  if (uiVersionWatchRegistered) return
  uiVersionWatchRegistered = true
  const uiStore = useUIStore()
  watch(
    () => uiStore.uiVersion,
    (v) => {
      if (v !== 'international') {
        canvasVirtualKeyboardOpen.value = false
      }
    }
  )
}
