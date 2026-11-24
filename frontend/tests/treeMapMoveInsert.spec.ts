/**
 * Tree-map branch moves insert at the drop target instead of swapping.
 */
import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'
import {
  readTreeLeafIndex,
  readTreeParentCategoryId,
  treeMapColumnsOf,
} from '@/utils/treeMapIdentity'

function loadSample(): ReturnType<typeof useDiagramStore> {
  const store = useDiagramStore()
  store.loadFromSpec(
    {
      root: {
        text: 'Root',
        children: [
          { text: 'Cat A', children: [{ text: 'A1' }, { text: 'A2' }, { text: 'A3' }] },
          { text: 'Cat B', children: [{ text: 'B1' }] },
          { text: 'Cat C', children: [{ text: 'C1' }] },
        ],
      },
      dimension: 'Kind',
    },
    'tree_map'
  )
  return store
}

function idByText(store: ReturnType<typeof useDiagramStore>, text: string): string {
  const node = store.data?.nodes?.find((n) => n.text === text)
  if (!node?.id) throw new Error(`missing ${text}`)
  return node.id
}

describe('tree map move insert', () => {
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

  it('inserts a category before the target instead of swapping', () => {
    const store = loadSample()
    const catC = idByText(store, 'Cat C')
    const catA = idByText(store, 'Cat A')
    expect(store.moveTreeMapBranch(catC, 'before', catA)).toBe(true)
    const columns = treeMapColumnsOf(store.data?.nodes ?? [])
    expect(columns.map((c) => c.category.text)).toEqual(['Cat C', 'Cat A', 'Cat B'])
  })

  it('inserts a category after the target', () => {
    const store = loadSample()
    const catA = idByText(store, 'Cat A')
    const catC = idByText(store, 'Cat C')
    expect(store.moveTreeMapBranch(catA, 'after', catC)).toBe(true)
    const columns = treeMapColumnsOf(store.data?.nodes ?? [])
    expect(columns.map((c) => c.category.text)).toEqual(['Cat B', 'Cat C', 'Cat A'])
  })

  it('inserts a leaf before another leaf in the same column', () => {
    const store = loadSample()
    const a3 = idByText(store, 'A3')
    const a1 = idByText(store, 'A1')
    expect(store.moveTreeMapBranch(a3, 'before', a1)).toBe(true)
    const column = treeMapColumnsOf(store.data?.nodes ?? [])[0]
    expect(column.leaves.map((leaf) => leaf.text)).toEqual(['A3', 'A1', 'A2'])
    expect(readTreeLeafIndex(column.leaves[0])).toBe(0)
  })

  it('moves a leaf into another category at the insert index', () => {
    const store = loadSample()
    const a2 = idByText(store, 'A2')
    const b1 = idByText(store, 'B1')
    expect(store.moveTreeMapBranch(a2, 'after', b1)).toBe(true)
    const columns = treeMapColumnsOf(store.data?.nodes ?? [])
    expect(columns[0].leaves.map((leaf) => leaf.text)).toEqual(['A1', 'A3'])
    expect(columns[1].leaves.map((leaf) => leaf.text)).toEqual(['B1', 'A2'])
    expect(readTreeParentCategoryId(columns[1].leaves[1])).toBe(columns[1].category.id)
  })
})
