/**
 * Canvas input mode for this browser.
 * Local storage paints immediately. The signed-in device row in Postgres wins.
 */
import { ref } from 'vue'

import { CANVAS_INPUT_MODE_KEY, readCanvasInputMode } from '@/config/canvasInputMode'
import type { CanvasInputMode } from '@/config/canvasInputMode'
import { fetchCanvasInputDevice, saveCanvasInputDevice } from '@/utils/canvasInputDevicePref'

export function createCanvasInputMode() {
  const canvasInputMode = ref<CanvasInputMode>('laptop')
  /** Choices made on this page. A later login writes them instead of restoring an older row. */
  let localEdits = 0

  function readCanvasInputFromStorage(): void {
    canvasInputMode.value = readCanvasInputMode(localStorage)
    localStorage.setItem(CANVAS_INPUT_MODE_KEY, canvasInputMode.value)
  }

  function setCanvasInputMode(value: CanvasInputMode, options?: { syncRemote?: boolean }): void {
    if (canvasInputMode.value === value) return
    canvasInputMode.value = value
    localStorage.setItem(CANVAS_INPUT_MODE_KEY, value)
    localEdits += 1
    if (options?.syncRemote !== false) {
      void saveCanvasInputDevice(value)
    }
  }

  /**
   * The device row wins when this page has not changed the segment.
   * A choice made before login is written so a classroom board is recorded.
   */
  async function hydrateCanvasInputFromDevice(): Promise<void> {
    const editsAtStart = localEdits
    const remote = await fetchCanvasInputDevice()
    if (localEdits !== editsAtStart) {
      await saveCanvasInputDevice(canvasInputMode.value)
      return
    }
    if (remote === 'unavailable') return
    if (remote === 'missing' || editsAtStart > 0) {
      await saveCanvasInputDevice(canvasInputMode.value)
      return
    }
    canvasInputMode.value = remote
    localStorage.setItem(CANVAS_INPUT_MODE_KEY, remote)
  }

  function markCanvasInputDeviceStale(): void {
    localEdits = 0
  }

  return {
    canvasInputMode,
    readCanvasInputFromStorage,
    setCanvasInputMode,
    hydrateCanvasInputFromDevice,
    markCanvasInputDeviceStale,
  }
}
