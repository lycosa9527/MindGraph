import { computed, inject } from 'vue'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { isSessionMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'

import { MIND_MAP_CANVAS_VARIANT_KEY } from './mindMapCanvasVariantKey'

/**
 * True when the active mind map should use v2 visual design (themes, shapes, orthogonal edges).
 * Prefers the locked variant from MindMapLegacyCanvas / MindMapV2Canvas when provided.
 * Canvas mode comes from the injected DiagramSession (Showcase owns gallery policy).
 */
export function useMindMapCanvasVisuals() {
  const injectedVariant = inject(MIND_MAP_CANVAS_VARIANT_KEY, null)
  const diagramStore = useDiagramSession()

  return computed(() => {
    const locked = injectedVariant?.value
    if (locked === 'v2') {
      return diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map'
    }
    if (locked === 'legacy') {
      return false
    }
    return (
      (diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map') &&
      isSessionMindMapV2VisualDesignActive(diagramStore.mindMapCanvasMode)
    )
  })
}
