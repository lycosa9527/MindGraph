import { computed } from 'vue'

import { useDiagramStore, useFeatureFlagsStore, useUIStore } from '@/stores'
import { isMindMapV2CanvasActive } from '@/utils/mindMapCanvasMode'

/** True when the mind map uses the new canvas chrome (Option 2 in Language & prompts). */
export function useMindMapV2Chrome() {
  const diagramStore = useDiagramStore()
  const uiStore = useUIStore()
  const featureFlagsStore = useFeatureFlagsStore()

  return computed(() =>
    isMindMapV2CanvasActive(
      diagramStore.type,
      uiStore.mindMapCanvasMode,
      featureFlagsStore.getFeatureMindmapV2Canvas()
    )
  )
}
