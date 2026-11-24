import { describe, expect, it } from 'vitest'

import { layoutTreeMapAddHandles, resolveTreeMapAddSelectionKind } from '@/utils/treeMapAddHandles'
import { TREE_TOPIC_NODE_ID } from '@/utils/treeMapIdentity'

const rect = {
  left: 100,
  top: 200,
  right: 220,
  bottom: 260,
  width: 120,
  height: 60,
}

describe('treeMapAddHandles', () => {
  it('resolves topic, category, and leaf selection kinds', () => {
    expect(resolveTreeMapAddSelectionKind({ id: TREE_TOPIC_NODE_ID, type: 'topic' })).toBe('topic')
    expect(
      resolveTreeMapAddSelectionKind({
        id: 'c1',
        type: 'branch',
        data: { nodeType: 'branch' },
      })
    ).toBe('category')
    expect(
      resolveTreeMapAddSelectionKind({
        id: 'l1',
        type: 'branch',
        data: { nodeType: 'leaf' },
      })
    ).toBe('leaf')
    expect(resolveTreeMapAddSelectionKind({ id: 'dimension-label', type: 'label' })).toBeNull()
  })

  it('places topic bottom, category L/B/R, leaf T/B handles', () => {
    expect(layoutTreeMapAddHandles('topic', rect)).toEqual([
      { action: 'category-after', left: 160, top: 260 },
    ])
    expect(layoutTreeMapAddHandles('category', rect)).toEqual([
      { action: 'category-before', left: 100, top: 230 },
      { action: 'leaf-append', left: 160, top: 260 },
      { action: 'category-after', left: 220, top: 230 },
    ])
    expect(layoutTreeMapAddHandles('leaf', rect)).toEqual([
      { action: 'leaf-before', left: 160, top: 200 },
      { action: 'leaf-after', left: 160, top: 260 },
    ])
  })
})
