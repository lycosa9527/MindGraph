import { describe, expect, it } from 'vitest'

import { isHierarchicalDropCandidate } from '@/composables/editor/useBranchMoveDrag'

describe('isHierarchicalDropCandidate', () => {
  const uuid = '0292ae97-f986-4945-9b45-a175bd5a92b5'
  const nodes = [
    { id: 'topic', type: 'topic' },
    { id: uuid, type: 'branch' },
    { id: 'branch-r-1-0', type: 'branch' },
  ]

  it('accepts UUID mind-map branches after identity migrate', () => {
    expect(isHierarchicalDropCandidate('mindmap', uuid, 'topic', nodes)).toBe(true)
  })

  it('still accepts leftover positional branch ids', () => {
    expect(isHierarchicalDropCandidate('mindmap', 'branch-r-1-0', 'topic', nodes)).toBe(true)
  })

  it('rejects the topic and unknown ids', () => {
    expect(isHierarchicalDropCandidate('mindmap', 'topic', 'topic', nodes)).toBe(false)
    expect(isHierarchicalDropCandidate('mindmap', uuid, 'topic', [])).toBe(false)
  })

  it('keeps tree-map prefix matching', () => {
    expect(isHierarchicalDropCandidate('tree_map', 'tree-cat-0', 'tree-topic')).toBe(true)
    expect(isHierarchicalDropCandidate('tree_map', uuid, 'tree-topic', nodes)).toBe(false)
  })
})
