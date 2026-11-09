/**
 * Insert controls for the ribbon and the classroom remote.
 * Mind maps keep child and sibling. Each thinking map uses the add the classic toolbar already ran.
 */
import { isThinkingMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'

export type DiagramInsertActionId =
  | 'child'
  | 'sibling'
  | 'node'
  | 'cause'
  | 'effect'
  | 'pair'
  | 'step'
  | 'substep'
  | 'branch'
  | 'leaf'
  | 'part'
  | 'subpart'
  | 'nextLevel'
  | 'similarity'
  | 'difference'

/** Glyph drawn for an insert button. The purple stroke is the node being added. */
export type DiagramInsertGlyph =
  | 'child'
  | 'sibling'
  | 'step'
  | 'substep'
  | 'branch'
  | 'leaf'
  | 'part'
  | 'subpart'
  | 'nextLevel'
  | 'similarity'
  | 'difference'
  | 'cause'
  | 'effect'

export type DiagramInsertAction = {
  id: DiagramInsertActionId
  labelKey: string
  /** Mind-map and level-add glyphs. Other adds use a plain plus. */
  insertKind?: DiagramInsertGlyph
  /** Keys shown on the button and in the shortcut guide. First key is the row id. */
  shortcutKeys?: readonly string[]
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
        shortcutKeys: ['Tab', 'Insert'],
        needsSelection: true,
      },
      {
        id: 'sibling',
        labelKey: 'canvas.toolbar.addSiblingNode',
        insertKind: 'sibling',
        shortcutKeys: ['Enter'],
        needsSelection: true,
      },
    ]
  }
  if (type === 'tree_map') {
    return [
      {
        id: 'branch',
        labelKey: 'canvas.toolbar.addBranch',
        insertKind: 'branch',
        shortcutKeys: ['Enter'],
        needsSelection: false,
      },
      {
        id: 'leaf',
        labelKey: 'canvas.toolbar.addTreeItem',
        insertKind: 'leaf',
        shortcutKeys: ['Tab'],
        needsSelection: false,
      },
    ]
  }
  if (type === 'brace_map') {
    return [
      {
        id: 'part',
        labelKey: 'canvas.toolbar.addPart',
        insertKind: 'part',
        shortcutKeys: ['Enter'],
        needsSelection: false,
      },
      {
        id: 'subpart',
        labelKey: 'canvas.toolbar.addSubpart',
        insertKind: 'subpart',
        shortcutKeys: ['Tab'],
        needsSelection: false,
      },
      {
        id: 'nextLevel',
        labelKey: 'canvas.toolbar.addNextLevel',
        insertKind: 'nextLevel',
        needsSelection: false,
      },
    ]
  }
  if (type === 'double_bubble_map') {
    return [
      {
        id: 'similarity',
        labelKey: 'canvas.toolbar.addSimilarity',
        insertKind: 'similarity',
        shortcutKeys: ['Enter'],
        needsSelection: false,
      },
      {
        id: 'difference',
        labelKey: 'canvas.toolbar.addDifference',
        insertKind: 'difference',
        shortcutKeys: ['Tab'],
        needsSelection: false,
      },
    ]
  }
  if (type === 'flow_map') {
    return [
      {
        id: 'step',
        labelKey: 'canvas.toolbar.addStep',
        insertKind: 'step',
        shortcutKeys: ['Enter'],
        needsSelection: false,
      },
      {
        id: 'substep',
        labelKey: 'canvas.toolbar.addSubstep',
        insertKind: 'substep',
        shortcutKeys: ['Tab'],
        needsSelection: false,
      },
    ]
  }
  if (type === 'multi_flow_map') {
    return [
      {
        id: 'cause',
        labelKey: 'canvas.toolbar.addCause',
        insertKind: 'cause',
        shortcutKeys: ['Enter'],
        needsSelection: false,
      },
      {
        id: 'effect',
        labelKey: 'canvas.toolbar.addEffect',
        insertKind: 'effect',
        shortcutKeys: ['Tab'],
        needsSelection: false,
      },
    ]
  }
  if (type === 'bridge_map') {
    return [
      {
        id: 'pair',
        labelKey: 'canvas.toolbar.addAnalogyPair',
        shortcutKeys: ['Enter'],
        needsSelection: false,
      },
    ]
  }
  if (type === 'concept_map') {
    return [{ id: 'node', labelKey: 'canvas.toolbar.addNode', needsSelection: false }]
  }
  if (isThinkingMapDiagramType(type)) {
    return [
      {
        id: 'node',
        labelKey: 'canvas.toolbar.addNode',
        shortcutKeys: ['Enter'],
        needsSelection: false,
      },
    ]
  }
  return []
}
