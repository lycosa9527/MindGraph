import { describe, expect, it } from 'vitest'

import { findMindMapNodeIdByLabel } from '@/utils/findMindMapNodeIdByLabel'
import type { Connection, DiagramNode } from '@/types'

describe('findMindMapNodeIdByLabel', () => {
  it('returns the matching non-topic node id', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: '宜家IKEA', type: 'topic' },
      { id: 'b1', text: '中国', type: 'branch' },
    ]
    const connections: Connection[] = [{ id: 'c1', source: 'topic', target: 'b1' }]
    expect(findMindMapNodeIdByLabel(nodes, connections, '中国')).toBe('b1')
  })

  it('prefers topic children when duplicate labels exist', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: '宜家IKEA', type: 'topic' },
      { id: 'b1', text: '中国', type: 'branch' },
      { id: 'c1', text: '中国', type: 'child' },
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'b1' },
      { id: 'e2', source: 'b1', target: 'c1' },
    ]
    expect(findMindMapNodeIdByLabel(nodes, connections, '中国')).toBe('b1')
  })

  it('returns null when label is missing', () => {
    const nodes: DiagramNode[] = [{ id: 'topic', text: '宜家IKEA', type: 'topic' }]
    expect(findMindMapNodeIdByLabel(nodes, [], '中国')).toBeNull()
  })
})
