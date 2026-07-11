/**
 * Apply Hub / live_context diagram_data to Pinia (desktop observer recovery).
 * Prefer canonical nodes+connections when present so flat children[] cannot
 * clobber a verified Pinia tree via stale nested nodes[].
 */
import { isDiagramWriteLocked } from '@/composables/kitty/useDiagramWriteLock'
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

/**
 * Build a loadFromSpec payload that prefers Pinia-canonical nodes/connections.
 * When both nodes[] and children[] exist, drop children so loadSpecForDiagramType
 * does not rebuild from a flat voice index that lost hierarchy.
 */
export function canonicalizeLiveContextDiagramData(
  diagramData: Record<string, unknown>
): Record<string, unknown> {
  const nodes = diagramData.nodes
  const connections = diagramData.connections
  if (Array.isArray(nodes) && nodes.length > 0) {
    const next: Record<string, unknown> = { ...diagramData, nodes }
    if (Array.isArray(connections)) {
      next.connections = connections
    }
    delete next.children
    return next
  }
  return { ...diagramData }
}

export function syncDiagramStoreFromVoiceContext(
  diagramTypeRaw: string,
  diagramData: Record<string, unknown> | null | undefined
): boolean {
  if (isDiagramWriteLocked()) {
    return false
  }
  const dt = normalizeDiagramType(diagramTypeRaw)
  if (dt == null || diagramData == null || !isRecord(diagramData)) {
    return false
  }
  const diagramStore = useDiagramStore()
  diagramStore.clearHistory()
  return diagramStore.loadFromSpec(canonicalizeLiveContextDiagramData(diagramData), dt)
}
