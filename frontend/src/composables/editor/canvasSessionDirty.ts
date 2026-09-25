/**
 * Desktop canvas autosave publishes dirty here so surfaces outside CanvasPage
 * (the quick-access remote) can confirm before replacing the open diagram.
 */
import { type Ref, ref } from 'vue'

const canvasSessionDirty = ref(false)

export function publishCanvasSessionDirty(value: boolean): void {
  canvasSessionDirty.value = value
}

export function useCanvasSessionDirty(): Ref<boolean> {
  return canvasSessionDirty
}
