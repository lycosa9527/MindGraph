/**
 * Insert controls for the ribbon and the classroom remote.
 * Mind maps keep child and sibling. Each thinking map uses the add the classic toolbar already ran.
 */
import { isThinkingMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'

export type DiagramInsertActionId = 'child' | 'sibling' | 'node' | 'cause' | 'effect' | 'pair'

export type DiagramInsertAction = {
  id: DiagramInsertActionId
  labelKey: string
  /** Mind-map glyph. Other adds use a plain plus. */
  insertKind?: 'child' | 'sibling'
  /** Dim until a node is selected. Thinking-map adds can start from the center. */
  needsSelection: boolean
}

export function diagramInsertActions(
  type: string | null | undefined
): readonly DiagramInsertAction[] {
  if (type === 'mindmap' || type === 'mind_map') {
    return [
      {
        id: 'child',
        labelKey: 'canvas.toolbar.addChildNode',
        insertKind: 'child',
        needsSelection: true,
      },
      {
        id: 'sibling',
        labelKey: 'canvas.toolbar.addSiblingNode',
        insertKind: 'sibling',
        needsSelection: true,
      },
    ]
  }
  if (type === 'multi_flow_map') {
    return [
      { id: 'cause', labelKey: 'canvas.toolbar.addCause', needsSelection: false },
      { id: 'effect', labelKey: 'canvas.toolbar.addEffect', needsSelection: false },
    ]
  }
  if (type === 'bridge_map') {
    return [{ id: 'pair', labelKey: 'canvas.toolbar.addAnalogyPair', needsSelection: false }]
  }
  if (type === 'concept_map') {
    return [{ id: 'node', labelKey: 'canvas.toolbar.addNode', needsSelection: false }]
  }
  if (isThinkingMapDiagramType(type)) {
    return [{ id: 'node', labelKey: 'canvas.toolbar.addNode', needsSelection: false }]
  }
  return []
}
