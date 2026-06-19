/**
 * Load full library spec into Pinia (mobile Kitty preview / picker).
 */
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import { useDiagramStore } from '@/stores/diagram'
import { VALID_DIAGRAM_TYPES } from '@/stores/diagram/constants'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'

function normalizeDiagramType(raw: string): DiagramType | null {
  const slug = raw.trim() === 'mind_map' ? 'mindmap' : raw.trim()
  if (!slug || !VALID_DIAGRAM_TYPES.includes(slug as DiagramType)) {
    return null
  }
  return slug as DiagramType
}

/**
 * Fetch saved diagram from library API and hydrate Pinia with full Vue Flow spec.
 */
export async function hydrateMobileKittyFromLibrary(diagramId: string): Promise<boolean> {
  const trimmed = diagramId.trim()
  if (!trimmed) {
    return false
  }
  const savedDiagramsStore = useSavedDiagramsStore()
  const diagramStore = useDiagramStore()
  const diagram = await savedDiagramsStore.getDiagram(trimmed)
  if (!diagram.ok) {
    return false
  }
  const dt = normalizeDiagramType(String(diagram.diagram.diagram_type ?? ''))
  if (dt == null) {
    return false
  }
  const spec = diagram.diagram.spec
  if (spec == null || typeof spec !== 'object') {
    return false
  }
  savedDiagramsStore.setActiveDiagram(trimmed)
  diagramStore.clearHistory()
  const ok = diagramStore.loadFromSpec(spec as Record<string, unknown>, dt)
  traceKittyWorkflow('mobile', 'library_hydrate', ok ? `ok type=${dt}` : 'load failed', {
    scope: trimmed,
  })
  return ok
}
