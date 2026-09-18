import { ref } from 'vue'

export type CanvasGuideId = 'shortcut' | 'gesture'

const activeCanvasGuideId = ref<CanvasGuideId | null>(null)

export function isCanvasGuideOpen(id: CanvasGuideId): boolean {
  return activeCanvasGuideId.value === id
}

export function toggleCanvasGuide(id: CanvasGuideId): boolean {
  if (activeCanvasGuideId.value === id) {
    activeCanvasGuideId.value = null
    return false
  }
  activeCanvasGuideId.value = id
  return true
}

export function openCanvasGuide(id: CanvasGuideId): void {
  activeCanvasGuideId.value = id
}

export { activeCanvasGuideId }
