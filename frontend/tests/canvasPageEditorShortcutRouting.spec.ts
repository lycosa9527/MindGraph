import { describe, expect, it } from 'vitest'

import {
  resolveEnterKeyEvent,
  resolveTabKeyEvent,
} from '@/composables/canvasPage/canvasPageEditorShortcutRouting'
import type { DiagramType } from '@/types'

/** Full diagram-type matrix for canvas keyboard routing (desktop CanvasPage). */
const ALL_DIAGRAM_TYPES: DiagramType[] = [
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
  'bridge_map',
  'concept_map',
  'mindmap',
  'mind_map',
  'diagram',
]

const TAB_EXPECTED: Record<DiagramType, ReturnType<typeof resolveTabKeyEvent>> = {
  circle_map: 'diagram:add_node_requested',
  bubble_map: 'diagram:add_node_requested',
  double_bubble_map: 'diagram:add_node_requested',
  tree_map: 'diagram:add_node_requested',
  brace_map: 'diagram:add_branch_requested',
  flow_map: 'diagram:add_branch_requested',
  multi_flow_map: 'diagram:add_node_requested',
  bridge_map: 'diagram:add_node_requested',
  concept_map: null,
  mindmap: 'diagram:add_child_requested',
  mind_map: 'diagram:add_child_requested',
  diagram: 'diagram:add_node_requested',
}

const ENTER_EXPECTED: Record<DiagramType, ReturnType<typeof resolveEnterKeyEvent>> = {
  circle_map: 'diagram:add_node_requested',
  bubble_map: 'diagram:add_node_requested',
  double_bubble_map: 'diagram:add_node_requested',
  tree_map: 'diagram:add_node_requested',
  brace_map: 'diagram:add_child_requested',
  flow_map: 'diagram:add_child_requested',
  multi_flow_map: 'diagram:add_node_requested',
  bridge_map: 'diagram:add_node_requested',
  concept_map: null,
  mindmap: 'diagram:add_sibling_requested',
  mind_map: 'diagram:add_sibling_requested',
  diagram: 'diagram:add_node_requested',
}

describe('canvasPageEditorShortcutRouting — all diagram types', () => {
  it.each(ALL_DIAGRAM_TYPES)('Tab routing for %s', (diagramType) => {
    expect(resolveTabKeyEvent(diagramType)).toBe(TAB_EXPECTED[diagramType])
  })

  it.each(ALL_DIAGRAM_TYPES)('Enter routing for %s', (diagramType) => {
    expect(resolveEnterKeyEvent(diagramType)).toBe(ENTER_EXPECTED[diagramType])
  })

  it('returns null Tab/Enter when diagram type is unset', () => {
    expect(resolveTabKeyEvent(null)).toBeNull()
    expect(resolveTabKeyEvent(undefined)).toBeNull()
    expect(resolveEnterKeyEvent(null)).toBeNull()
    expect(resolveEnterKeyEvent(undefined)).toBeNull()
  })
})

/** Global shortcuts — same handler on CanvasPage for every diagram type (except where noted). */
describe('canvas global shortcuts (type-agnostic on CanvasPage)', () => {
  it('documents concept_map as the only type with Tab/Enter/= add blocked', () => {
    expect(resolveTabKeyEvent('concept_map')).toBeNull()
    expect(resolveEnterKeyEvent('concept_map')).toBeNull()
  })

  it('covers every DiagramType in Tab and Enter matrices', () => {
    for (const type of ALL_DIAGRAM_TYPES) {
      expect(TAB_EXPECTED).toHaveProperty(type)
      expect(ENTER_EXPECTED).toHaveProperty(type)
    }
  })
})
