/**
 * Apply voice-shaped diagram_data from live_context to Pinia (desktop recovery).
 */
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

export function syncDiagramStoreFromVoiceContext(
  diagramTypeRaw: string,
  diagramData: Record<string, unknown> | null | undefined
): boolean {
  const dt = normalizeDiagramType(diagramTypeRaw)
  if (dt == null || diagramData == null || typeof diagramData !== 'object') {
    return false
  }
  const diagramStore = useDiagramStore()
  diagramStore.clearHistory()
  return diagramStore.loadFromSpec({ ...diagramData }, dt)
}
