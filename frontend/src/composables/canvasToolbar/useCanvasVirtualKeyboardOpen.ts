import { ref, watch } from 'vue'

import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import { useUIStore } from '@/stores/ui'

/**
 * Single open flag for {@link CanvasVirtualKeyboardPanel}, shared by the main
 * toolbar “more apps” entry and the presentation side rail (Ctrl+6 / slot 6).
 * New canvas (V2 chrome) does not expose the keyboard.
 */
export const canvasVirtualKeyboardOpen = ref(false)

let uiVersionWatchRegistered = false
let newCanvasChromeActive = false

export function toggleCanvasVirtualKeyboard(): void {
  if (newCanvasChromeActive) {
    canvasVirtualKeyboardOpen.value = false
    return
  }
  canvasVirtualKeyboardOpen.value = !canvasVirtualKeyboardOpen.value
}

/**
 * When UI is not international, or New canvas chrome is active, keep the panel
 * closed. Idempotent so multiple {@link useCanvasToolbarApps} callers register
 * at most one watcher.
 */
export function ensureCanvasVirtualKeyboardUiVersionSync(): void {
  if (uiVersionWatchRegistered) return
  uiVersionWatchRegistered = true
  const uiStore = useUIStore()
  const useMindMapV2 = useMindMapV2Chrome()
  watch(
    () => uiStore.uiVersion,
    (v) => {
      if (v !== 'international') {
        canvasVirtualKeyboardOpen.value = false
      }
    }
  )
  watch(
    useMindMapV2,
    (v2) => {
      newCanvasChromeActive = v2
      if (v2) {
        canvasVirtualKeyboardOpen.value = false
      }
    },
    { immediate: true }
  )
}
