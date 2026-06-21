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

/** Tab key routing when not typing in an input (matches useCanvasPageEditorShortcuts). */
export function resolveTabKeyEvent(
  diagramType: string | null | undefined
): CanvasPageShortcutEvent | null {
  if (!diagramType || diagramType === 'concept_map') {
    return null
  }
  if (isMindMapDiagramType(diagramType)) {
    return 'diagram:add_child_requested'
  }
  if (diagramType === 'brace_map' || diagramType === 'flow_map') {
    return 'diagram:add_branch_requested'
  }
  return 'diagram:add_node_requested'
}

/** Enter key routing when not typing in an input (matches useCanvasPageEditorShortcuts). */
export function resolveEnterKeyEvent(
  diagramType: string | null | undefined
): CanvasPageShortcutEvent | null {
  if (!diagramType || diagramType === 'concept_map') {
    return null
  }
  if (isMindMapDiagramType(diagramType)) {
    return 'diagram:add_sibling_requested'
  }
  if (diagramType === 'tree_map' || diagramType === 'multi_flow_map') {
    return 'diagram:add_node_requested'
  }
  if (diagramType === 'brace_map' || diagramType === 'flow_map') {
    return 'diagram:add_child_requested'
  }
  if (ENTER_ADD_NODE_TYPES.has(diagramType)) {
    return 'diagram:add_node_requested'
  }
  return null
}
