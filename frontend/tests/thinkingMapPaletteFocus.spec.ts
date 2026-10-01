import { describe, expect, it } from 'vitest'

import { thinkingMapPaletteFocus } from '@/composables/nodePalette/thinkingMapPaletteFocus'

describe('thinkingMapPaletteFocus', () => {
  it('opens circle maps on the palette default', () => {
    expect(
      thinkingMapPaletteFocus({
        diagramType: 'circle_map',
        nodes: [{ id: 'ctx-1', text: '叶绿体', type: 'bubble' }],
        nodeId: 'ctx-1',
      })
    ).toBeNull()
  })

  it('focuses a multi-flow cause on the causes tab', () => {
    expect(
      thinkingMapPaletteFocus({
        diagramType: 'multi_flow_map',
        nodes: [{ id: 'c1', text: '堵车', data: { multiFlowRole: 'cause' } }],
        nodeId: 'c1',
      })
    ).toEqual({ kind: 'mode', mode: 'causes' })
  })

  it('focuses a tree category on its children stage', () => {
    const focus = thinkingMapPaletteFocus({
      diagramType: 'tree_map',
      nodes: [{ id: 'cat-1', text: '动物', data: { nodeType: 'branch' } }],
      connections: [{ source: 'tree-topic', target: 'cat-1' }],
      nodeId: 'cat-1',
    })
    expect(focus).toMatchObject({
      kind: 'parent',
      id: 'cat-1',
      name: '动物',
      stage: 'children',
    })
  })
})
