/**
 * Add and delete keep live ids, restamp dense indexes, and rebuild the vertical chain.
 */
import { describe, expect, it } from 'vitest'

import {
  appendTreeMapCategory,
  appendTreeMapChild,
  arrangeTreeMapNodes,
  materializeTreeMapGraph,
  removeTreeMapGraphNodes,
} from '@/stores/diagram/treeMapStructure'
import { loadTreeMapSpec, recalculateTreeMapLayout } from '@/stores/specLoader/treeMap'
import type { DiagramNode } from '@/types'
import {
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
  readTreeCategoryIndex,
  readTreeLeafIndex,
  readTreeParentCategoryId,
} from '@/utils/treeMapIdentity'

function sample() {
  return loadTreeMapSpec({
    root: {
      text: 'Root',
      children: [
        { text: 'Cat A', children: [{ text: 'A1' }, { text: 'A2' }, { text: 'A3' }] },
        { text: 'Cat B', children: [{ text: 'B1' }] },
      ],
    },
    dimension: 'Kind',
  })
}

function byText(nodes: DiagramNode[], text: string): DiagramNode {
  const found = nodes.find((node) => node.text === text)
  if (!found?.id) throw new Error(`missing ${text}`)
  return found
}

describe('tree map structure edits', () => {
  it('appends a category without replacing existing ids', () => {
    const loaded = sample()
    const beforeIds = loaded.nodes.map((node) => node.id)
    const catA = byText(loaded.nodes, 'Cat A')
    catA.style = { ...catA.style, fontSize: 22, backgroundColor: '#abcdef' }
    catA.textSecondary = 'gloss'
    catA.data = { ...catA.data, hiddenAnswer: 'secret' }

    const next = appendTreeMapCategory(loaded.nodes, 'Cat C')
    if (!next) throw new Error('append failed')

    expect(next.nodes.map((node) => node.id)).toEqual(expect.arrayContaining(beforeIds))
    const kept = byText(next.nodes, 'Cat A')
    expect(kept.id).toBe(catA.id)
    expect(kept.style?.fontSize).toBe(22)
    expect(kept.style?.backgroundColor).toBe('#abcdef')
    expect(kept.textSecondary).toBe('gloss')
    expect(kept.data?.hiddenAnswer).toBe('secret')

    const added = byText(next.nodes, 'Cat C')
    expect(isTreeMapCategoryNode(added)).toBe(true)
    expect(readTreeCategoryIndex(added)).toBe(2)
    expect(
      next.connections.some((edge) => edge.source === 'tree-topic' && edge.target === added.id)
    ).toBe(true)

    const laidOut = recalculateTreeMapLayout(next.nodes, {})
    const rowY = byText(laidOut, 'Cat A').position?.y
    expect(byText(laidOut, 'Cat C').position?.y).toBe(rowY)
    expect(byText(laidOut, 'Cat C').position?.x).not.toBe(byText(laidOut, 'Cat A').position?.x)
  })

  it('chains a new leaf under the previous leaf and stacks it below', () => {
    const loaded = sample()
    const catA = byText(loaded.nodes, 'Cat A')
    const next = appendTreeMapChild(loaded.nodes, catA.id, 'A4')
    if (!next) throw new Error('append child failed')
    const added = byText(next.nodes, 'A4')
    const previous = byText(next.nodes, 'A3')
    expect(readTreeParentCategoryId(added)).toBe(catA.id)
    expect(readTreeLeafIndex(added)).toBe(3)
    expect(
      next.connections.some((edge) => edge.source === previous.id && edge.target === added.id)
    ).toBe(true)

    const laidOut = recalculateTreeMapLayout(next.nodes, {})
    const leaf = byText(laidOut, 'A4')
    const above = byText(laidOut, 'A3')
    const aboveBottom = (above.position?.y ?? 0) + (above.style?.height ?? 0)
    const center = (node: DiagramNode): number =>
      (node.position?.x ?? 0) + (typeof node.style?.width === 'number' ? node.style.width : 0) / 2
    expect(leaf.position?.y ?? 0).toBeGreaterThanOrEqual(aboveBottom - 0.5)
    expect(center(leaf)).toBeCloseTo(center(above), 3)
  })

  it('reconnects the chain when a middle leaf is deleted', () => {
    const loaded = sample()
    const middle = byText(loaded.nodes, 'A2')
    const next = removeTreeMapGraphNodes(loaded.nodes, [middle.id])
    if (!next) throw new Error('delete failed')
    expect(next.deletedIds).toEqual([middle.id])
    expect(next.nodes.some((node) => node.id === middle.id)).toBe(false)
    const a1 = byText(next.nodes, 'A1')
    const a3 = byText(next.nodes, 'A3')
    expect(readTreeLeafIndex(a1)).toBe(0)
    expect(readTreeLeafIndex(a3)).toBe(1)
    expect(next.connections.some((edge) => edge.source === a1.id && edge.target === a3.id)).toBe(
      true
    )
    expect(
      next.connections.some((edge) => edge.target === middle.id || edge.source === middle.id)
    ).toBe(false)
  })

  it('removes a category with its leaves and closes the index gap', () => {
    const loaded = sample()
    const catA = byText(loaded.nodes, 'Cat A')
    const next = removeTreeMapGraphNodes(loaded.nodes, [catA.id])
    if (!next) throw new Error('delete category failed')
    expect(next.nodes.some((node) => node.text === 'Cat A' || node.text === 'A1')).toBe(false)
    expect(next.deletedIds).toEqual(
      expect.arrayContaining([
        catA.id,
        byText(loaded.nodes, 'A1').id,
        byText(loaded.nodes, 'A2').id,
      ])
    )
    const catB = byText(next.nodes, 'Cat B')
    expect(readTreeCategoryIndex(catB)).toBe(0)
    expect(isTreeMapLeafNode(byText(next.nodes, 'B1'))).toBe(true)
    expect(readTreeParentCategoryId(byText(next.nodes, 'B1'))).toBe(catB.id)
    expect(
      next.connections.some((edge) => edge.source === 'tree-topic' && edge.target === catB.id)
    ).toBe(true)
    const label = next.nodes.find((node) => node.id === 'dimension-label')
    expect(label?.text).toBe('Kind')
  })

  it('refuses to delete the topic', () => {
    const loaded = sample()
    expect(removeTreeMapGraphNodes(loaded.nodes, ['tree-topic'])).toBeNull()
  })

  it('follows a moved leaf and a swapped category instead of the old stamps', () => {
    const loaded = sample()
    const catA = byText(loaded.nodes, 'Cat A')
    const catB = byText(loaded.nodes, 'Cat B')
    const a1 = byText(loaded.nodes, 'A1')
    const moved = materializeTreeMapGraph(
      arrangeTreeMapNodes(loaded.nodes, [
        {
          id: catB.id,
          children: [{ id: byText(loaded.nodes, 'B1').id }, { id: a1.id }],
        },
        {
          id: catA.id,
          children: [{ id: byText(loaded.nodes, 'A2').id }, { id: byText(loaded.nodes, 'A3').id }],
        },
      ])
    )
    const nextB = byText(moved.nodes, 'Cat B')
    const nextA = byText(moved.nodes, 'Cat A')
    const movedLeaf = byText(moved.nodes, 'A1')
    expect(readTreeCategoryIndex(nextB)).toBe(0)
    expect(readTreeCategoryIndex(nextA)).toBe(1)
    expect(readTreeParentCategoryId(movedLeaf)).toBe(catB.id)
    expect(readTreeLeafIndex(movedLeaf)).toBe(1)
    expect(movedLeaf.style).toEqual(a1.style)
    expect(moved.nodes.find((node) => node.id === 'dimension-label')?.text).toBe('Kind')
  })
})
