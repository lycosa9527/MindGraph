import { describe, expect, it } from 'vitest'

import { keepEdgesForNodes } from '@/composables/diagramCanvas/useDiagramCanvasNodesEdges'

describe('keepEdgesForNodes', () => {
  it('drops edges whose source or target is not on the canvas yet', () => {
    const edges = [
      { id: 'edge-topic-a', source: 'topic', target: 'a' },
      { id: 'edge-a-b', source: 'a', target: 'b' },
    ]
    expect(keepEdgesForNodes(edges, new Set(['topic', 'a']))).toEqual([
      { id: 'edge-topic-a', source: 'topic', target: 'a' },
    ])
    expect(keepEdgesForNodes(edges, new Set())).toEqual([])
  })
})
