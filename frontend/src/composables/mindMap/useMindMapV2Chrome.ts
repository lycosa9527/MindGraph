import { computed } from 'vue'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import {
  isSessionMindMapV2VisualDesignActive,
  resolveSessionMindMapCanvasMode,
} from '@/utils/mindMapCanvasMode'

function isMindMapType(type: string | null | undefined): boolean {
  return type === 'mindmap' || type === 'mind_map'
}

/** True when the mind map uses New-canvas (V2) chrome. */
export function useMindMapV2Chrome() {
  const diagramStore = useDiagramSession()

  return computed(
    () =>
      isMindMapType(diagramStore.type) &&
      resolveSessionMindMapCanvasMode(diagramStore.mindMapCanvasMode) === 'v2'
  )
}

/** True when the mind map uses V3 bubble-style chrome (old JS top/bottom/property bars). */
export function useMindMapV3Chrome() {
  const diagramStore = useDiagramSession()

  return computed(
    () =>
      isMindMapType(diagramStore.type) &&
      resolveSessionMindMapCanvasMode(diagramStore.mindMapCanvasMode) === 'v3'
  )
}

/** True when the mind map uses V2 layout/theme (V2 or V3 chrome). */
export function useMindMapV2FamilyVisual() {
  const diagramStore = useDiagramSession()

  return computed(
    () =>
      isMindMapType(diagramStore.type) &&
      isSessionMindMapV2VisualDesignActive(diagramStore.mindMapCanvasMode)
  )
}
