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

/**
 * Tab adds a mind-map child.
 * Thinking maps do not use Tab; Enter adds a node after the click selection.
 */
export function resolveTabKeyEvent(
  diagramType: string | null | undefined
): CanvasPageShortcutEvent | null {
  if (!diagramType || diagramType === 'concept_map' || isThinkingMapDiagramType(diagramType)) {
    return null
  }
  if (isMindMapDiagramType(diagramType)) {
    return 'diagram:add_child_requested'
  }
  return 'diagram:add_node_requested'
}

/** Insert adds a mind-map child. Thinking maps do not use Insert. */
export function resolveInsertKeyEvent(
  diagramType: string | null | undefined
): CanvasPageShortcutEvent | null {
  if (isMindMapDiagramType(diagramType)) {
    return 'diagram:add_child_requested'
  }
  return null
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
