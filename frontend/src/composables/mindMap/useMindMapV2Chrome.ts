import { computed } from 'vue'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { isSessionMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'

/** True when the mind map uses the new canvas chrome (Option 2 in UI settings). */
export function useMindMapV2Chrome() {
  const diagramStore = useDiagramSession()

  return computed(
    () =>
      (diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map') &&
      isSessionMindMapV2VisualDesignActive(diagramStore.mindMapCanvasMode)
  )
}
