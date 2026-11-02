import { isThinkingMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'
import { isMindMapDiagramType } from '@/composables/mindMap/mindMapArrowNavigation'

export type CanvasPageShortcutEvent =
  | 'diagram:add_child_requested'
  | 'diagram:add_sibling_requested'
  | 'diagram:add_branch_requested'
  | 'diagram:add_node_requested'

/** Diagram types where Enter adds via the primary add-node path (same as toolbar +). */
const ENTER_ADD_NODE_TYPES = new Set([
  'bubble_map',
  'circle_map',
  'double_bubble_map',
  'bridge_map',
  'diagram',
])

/** Maps where Tab adds the second level and Enter adds the first. */
const TAB_NESTED_ADD_TYPES = new Set([
  'flow_map',
  'tree_map',
  'brace_map',
  'double_bubble_map',
  'multi_flow_map',
])

export function tabAddsNestedNode(diagramType: string | null | undefined): boolean {
  return typeof diagramType === 'string' && TAB_NESTED_ADD_TYPES.has(diagramType)
}

/**
 * Tab adds a mind-map child, or the second level on flow, tree, brace, double bubble, and cause-effect maps.
 * Other thinking maps do not use Tab. Enter adds the first level.
 */
export function resolveTabKeyEvent(
  diagramType: string | null | undefined
): CanvasPageShortcutEvent | null {
  if (!diagramType || diagramType === 'concept_map') return null
  if (tabAddsNestedNode(diagramType) || isMindMapDiagramType(diagramType)) {
    return 'diagram:add_child_requested'
  }
  if (isThinkingMapDiagramType(diagramType)) return null
  return 'diagram:add_node_requested'
}

/** Insert key: mind-map alias of Tab (add child). Other diagram types ignore Insert. */
export function resolveInsertKeyEvent(
  diagramType: string | null | undefined
): CanvasPageShortcutEvent | null {
  if (!isMindMapDiagramType(diagramType)) {
    return null
  }
  return 'diagram:add_child_requested'
}

/**
 * Enter adds a sibling on mind maps.
 * On thinking maps it adds a node for the current selection (same path as the toolbar add).
 */
export function resolveEnterKeyEvent(
  diagramType: string | null | undefined
): CanvasPageShortcutEvent | null {
  if (!diagramType || diagramType === 'concept_map') {
    return null
  }
  if (isMindMapDiagramType(diagramType)) {
    return 'diagram:add_sibling_requested'
  }
  if (isThinkingMapDiagramType(diagramType) || ENTER_ADD_NODE_TYPES.has(diagramType)) {
    return 'diagram:add_node_requested'
  }
  return null
}
