/**
 * Tab shell (title-row tabs, collapsible tools, status bar) for every diagram
 * editor. Mind-map v2 layout, themes, and orthogonal edges stay on
 * {@link useMindMapV2Chrome}.
 */
import { type ComputedRef, computed } from 'vue'
import { useRoute } from 'vue-router'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { VALID_DIAGRAM_TYPES } from '@/utils/diagramTypeKeys'

const RIBBON_TYPES = new Set<string>(VALID_DIAGRAM_TYPES)

export function useCanvasRibbonChrome(): ComputedRef<boolean> {
  const diagramStore = useDiagramSession()
  const route = useRoute()

  return computed(() => {
    const fromStore = diagramStore.type
    const fromRoute = typeof route.query.type === 'string' ? route.query.type : null
    const type = fromStore || fromRoute
    if (!type) return true
    return RIBBON_TYPES.has(type)
  })
}
