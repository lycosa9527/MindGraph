import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'

function nodeSide(nodeId: string): 'left' | 'right' | 'topic' {
  if (nodeId === 'topic') return 'topic'
  if (nodeId.startsWith('branch-l-')) return 'left'
  if (nodeId.startsWith('branch-r-')) return 'right'
  throw new Error(`unexpected node id: ${nodeId}`)
}

describe('mind map sibling selection anchor', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
  })

  function loadBranches(): { leftId: string; rightId: string } {
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('mindmap')

    const left = diagramStore.data?.nodes.find((node) => node.id.startsWith('branch-l-'))
    const right = diagramStore.data?.nodes.find((node) => node.id.startsWith('branch-r-'))
    if (!left || !right) {
      throw new Error('expected left and right branches in default mind map template')
    }
    return { leftId: left.id, rightId: right.id }
  }

  function newestSiblingNodeId(beforeIds: Set<string>): string {
    const diagramStore = useDiagramStore()
    const added = diagramStore.data?.nodes.find(
      (node) => node.id.startsWith('branch-') && !beforeIds.has(node.id)
    )
    if (!added) {
      throw new Error('expected a newly added branch node')
    }
    return added.id
  }

  it('adds sibling on the same side as the selected anchor branch', () => {
    const diagramStore = useDiagramStore()
    const { rightId } = loadBranches()
    const beforeIds = new Set(diagramStore.data?.nodes.map((node) => node.id) ?? [])

    diagramStore.selectNodes(rightId)
    expect(diagramStore.addMindMapSibling(rightId, 'Right sibling')).toBe(true)

    const newId = newestSiblingNodeId(beforeIds)
    expect(nodeSide(newId)).toBe('right')
  })

  it('uses stale left selection when anchor id is not updated (regression)', () => {
    const diagramStore = useDiagramStore()
    const { leftId, rightId } = loadBranches()
    const beforeIds = new Set(diagramStore.data?.nodes.map((node) => node.id) ?? [])

    diagramStore.selectNodes(leftId)
    expect(diagramStore.addMindMapSibling(leftId, 'Left sibling')).toBe(true)

    const newId = newestSiblingNodeId(beforeIds)
    expect(nodeSide(newId)).toBe('left')
    expect(newId).not.toBe(rightId)
  })
})
