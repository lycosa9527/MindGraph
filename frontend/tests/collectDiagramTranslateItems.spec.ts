import { describe, expect, it } from 'vitest'

import { collectDiagramTranslateItems } from '@/utils/collectDiagramTranslateItems'

describe('collectDiagramTranslateItems', () => {
  it('collects non-empty node and connection labels', () => {
    expect(
      collectDiagramTranslateItems({
        nodes: [
          { id: 'n1', text: 'Hello' },
          { id: 'n2', text: '  ' },
          { id: 'n3', data: { label: 'From data' } },
        ],
        connections: [
          { id: 'c1', label: 'leads to' },
          { id: 'c2', label: '' },
        ],
      })
    ).toEqual([
      { itemId: 'n1', text: 'Hello', kind: 'node' },
      { itemId: 'n3', text: 'From data', kind: 'node' },
      { itemId: 'c1', text: 'leads to', kind: 'connection' },
    ])
  })

  it('returns an empty list for missing or invalid source', () => {
    expect(collectDiagramTranslateItems(null)).toEqual([])
    expect(collectDiagramTranslateItems({})).toEqual([])
    expect(collectDiagramTranslateItems({ nodes: [{ text: 'no-id' }] })).toEqual([])
  })
})
