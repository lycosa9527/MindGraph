import { computed, inject } from 'vue'

import { useDiagramStore, useFeatureFlagsStore, useUIStore } from '@/stores'
import { isMindMapV2CanvasActive } from '@/utils/mindMapCanvasMode'

import { MIND_MAP_CANVAS_VARIANT_KEY } from './mindMapCanvasVariantKey'

/**
 * True when the active mind map should use v2 visual design (themes, shapes, orthogonal edges).
 * Prefers the locked variant from MindMapLegacyCanvas / MindMapV2Canvas when provided.
 */
export function useMindMapCanvasVisuals() {
  const injectedVariant = inject(MIND_MAP_CANVAS_VARIANT_KEY, null)
  const diagramStore = useDiagramStore()
  const uiStore = useUIStore()
  const featureFlagsStore = useFeatureFlagsStore()

  return computed(() => {
    const locked = injectedVariant?.value
    if (locked === 'v2') {
      return diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map'
    }
    if (locked === 'legacy') {
      return false
    }
    return isMindMapV2CanvasActive(
      diagramStore.type,
      uiStore.mindMapCanvasMode,
      featureFlagsStore.getFeatureMindmapV2Canvas()
    )
  })
}
