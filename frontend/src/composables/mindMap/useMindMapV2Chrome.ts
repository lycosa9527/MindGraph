import { computed } from 'vue'

import { useDiagramStore, useUIStore } from '@/stores'
import { isMindMapDiagramType } from '@/utils/conceptMapDesktopViewport'

/** True when the mind map uses the new canvas chrome (Option 2 in Language & prompts). */
export function useMindMapV2Chrome() {
  const diagramStore = useDiagramStore()
  const uiStore = useUIStore()

  return computed(
    () => isMindMapDiagramType(diagramStore.type) && uiStore.mindMapCanvasMode === 'v2'
  )
}
