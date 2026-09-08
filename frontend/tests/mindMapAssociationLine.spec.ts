import { describe, expect, it } from 'vitest'

import { buildMindMapChildrenMapByConnectionOrder } from '@/stores/diagram/mindMapStylePreservation'
import type { Connection } from '@/types'
import {
  MIND_MAP_ASSOCIATION_EDGE_TYPE,
  isMindMapAssociationConnection,
  mindMapTreeParentId,
} from '@/utils/mindMapLocation'

describe('mind map association connections', () => {
  const tree: Connection = { id: 'e1', source: 'topic', target: 'a' }
  const assoc: Connection = {
    id: 'assoc-1',
    source: 'a',
    target: 'b',
    edgeType: MIND_MAP_ASSOCIATION_EDGE_TYPE,
    label: 'leads to',
  }

  it('does not treat association overlays as tree parents', () => {
    expect(isMindMapAssociationConnection(assoc)).toBe(true)
    expect(mindMapTreeParentId([tree, assoc], 'a')).toBe('topic')
    expect(mindMapTreeParentId([tree, assoc], 'b')).toBeNull()
  })

  it('keeps association edges out of the children map', () => {
    const map = buildMindMapChildrenMapByConnectionOrder([tree, assoc])
    expect(map.get('topic')).toEqual(['a'])
    expect(map.get('a')).toBeUndefined()
  })
})
