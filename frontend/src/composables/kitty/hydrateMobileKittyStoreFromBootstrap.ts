/**
 * Lazy mobile Kitty Pinia hydrate from server bootstrap voice context (local UX only).
 * Does not fetch the library spec API — server already merged the library row.
 */
import type { KittyAgentContext } from '@/composables/kitty/useKittyAgent'
import { useDiagramStore } from '@/stores/diagram'
import { VALID_DIAGRAM_TYPES } from '@/stores/diagram/constants'
import type { DiagramType } from '@/types'

function normalizeDiagramType(raw: string): DiagramType | null {
  const slug = raw.trim() === 'mind_map' ? 'mindmap' : raw.trim()
  if (!slug || !VALID_DIAGRAM_TYPES.includes(slug as DiagramType)) {
    return null
  }
  return slug as DiagramType
}

/**
 * Populate Pinia from server-hydrated voice ``diagram_data`` when the store is empty.
 * Returns true when the store has diagram content after the call.
 */
export function hydrateMobileKittyStoreFromBootstrap(
  context: KittyAgentContext | null | undefined,
  diagramTypeHint: string
): boolean {
  const diagramStore = useDiagramStore()
  if (diagramStore.type != null && (diagramStore.data?.nodes?.length ?? 0) > 0) {
    return true
  }

  const dt =
    normalizeDiagramType(String(context?.diagram_type ?? diagramTypeHint)) ??
    normalizeDiagramType(diagramTypeHint)
  if (dt == null) {
    return false
  }

  const dd = context?.diagram_data
  if (dd == null || typeof dd !== 'object') {
    return false
  }

  diagramStore.clearHistory()
  return diagramStore.loadFromSpec({ ...dd }, dt)
}
