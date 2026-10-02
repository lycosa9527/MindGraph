import { describe, expect, it } from 'vitest'

import { showsNodeFloatingAiSubgraph } from '@/canvas-ribbon/nodeFloatingAiSubgraph'

describe('showsNodeFloatingAiSubgraph', () => {
  it('follows the AI tab and hides the mind-map center topic', () => {
    expect(showsNodeFloatingAiSubgraph('circle_map', false, 'n1')).toBe(false)
    expect(showsNodeFloatingAiSubgraph('bubble_map', false, 'n1')).toBe(false)
    expect(showsNodeFloatingAiSubgraph('flow_map', false, 'n1')).toBe(false)
    expect(showsNodeFloatingAiSubgraph('bridge_map', false, 'n1')).toBe(false)
    expect(showsNodeFloatingAiSubgraph('tree_map', false, 'n1')).toBe(true)
    expect(showsNodeFloatingAiSubgraph('brace_map', false, 'whole')).toBe(true)
    expect(showsNodeFloatingAiSubgraph('tree_map', false, null)).toBe(false)
    expect(showsNodeFloatingAiSubgraph('mindmap', true, 'topic')).toBe(false)
    expect(showsNodeFloatingAiSubgraph('mindmap', true, 'branch')).toBe(true)
    expect(showsNodeFloatingAiSubgraph('mindmap', false, 'branch')).toBe(false)
    expect(showsNodeFloatingAiSubgraph('concept_map', false, 'n1')).toBe(true)
  })
})
