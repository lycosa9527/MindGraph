import { describe, expect, it } from 'vitest'

import {
  isMindMapCollapseEligibleNode,
  resolveMindMapCollapseHoverNodeId,
} from '@/composables/canvasToolbar/useMindMapCollapseTogglePosition'
import type { Connection } from '@/types'

const connections: Connection[] = [
  { id: 'edge-topic-branch-r-1-0', source: 'topic', target: 'branch-r-1-0' },
  { id: 'edge-branch-r-1-0-branch-r-2-1', source: 'branch-r-1-0', target: 'branch-r-2-1' },
]

describe('mindMap collapse overlay target', () => {
  it('detects eligible branch nodes with children', () => {
    expect(isMindMapCollapseEligibleNode('branch-r-1-0', connections)).toBe(true)
    expect(isMindMapCollapseEligibleNode('branch-r-2-1', connections)).toBe(false)
    expect(isMindMapCollapseEligibleNode('topic', connections)).toBe(false)
  })

  it('resolves parent branch when hovering a connector edge', () => {
    const edge = document.createElement('g')
    edge.className = 'vue-flow__edge'
    edge.setAttribute('data-id', 'edge-branch-r-1-0-branch-r-2-1')
    const path = document.createElement('path')
    path.className = 'vue-flow__edge-path'
    edge.appendChild(path)

    expect(resolveMindMapCollapseHoverNodeId(path, connections)).toBe('branch-r-1-0')
  })

  it('resolves branch when hovering a node', () => {
    const node = document.createElement('div')
    node.className = 'vue-flow__node'
    node.setAttribute('data-id', 'branch-r-1-0')

    expect(resolveMindMapCollapseHoverNodeId(node, connections)).toBe('branch-r-1-0')
  })
})
