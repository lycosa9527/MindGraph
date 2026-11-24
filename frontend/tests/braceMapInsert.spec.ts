/**
 * Brace-map + handles insert a sibling at an index, or a child under that node.
 */
import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'
import { braceChildIds } from '@/utils/braceMapAddHandles'

function loadSample(): ReturnType<typeof useDiagramStore> {
  const store = useDiagramStore()
  store.loadFromSpec(
    {
      whole: '整体',
      parts: [
        { name: '部分A', subparts: [{ name: '子A1' }, { name: '子A2' }] },
        { name: '部分B', subparts: [{ name: '子B1' }] },
      ],
    },
    'brace_map'
  )
  return store
}

function idByText(store: ReturnType<typeof useDiagramStore>, text: string): string {
  const node = store.data?.nodes?.find((item) => item.text === text)
  if (!node?.id) throw new Error(`missing ${text}`)
  return node.id
}

function childTexts(store: ReturnType<typeof useDiagramStore>, parentId: string): string[] {
  const nodes = store.data?.nodes ?? []
  return braceChildIds(parentId, store.data?.connections ?? []).map(
    (id) => nodes.find((node) => node.id === id)?.text ?? id
  )
}

describe('brace map insert', () => {
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

  it('inserts a part before the selected part', () => {
    const store = loadSample()
    const wholeId = idByText(store, '整体')
    const beforeB = childTexts(store, wholeId).indexOf('部分B')
    const id = store.insertBraceMapChild(wholeId, '新部分', beforeB)
    expect(id).toBeTruthy()
    expect(childTexts(store, wholeId)).toEqual(['部分A', '新部分', '部分B'])
  })

  it('inserts a subpart between existing siblings', () => {
    const store = loadSample()
    const partA = idByText(store, '部分A')
    const beforeA2 = childTexts(store, partA).indexOf('子A2')
    expect(store.insertBraceMapChild(partA, '新子部分', beforeA2)).toBeTruthy()
    expect(childTexts(store, partA)).toEqual(['子A1', '新子部分', '子A2'])
  })

  it('attaches the next level under the selected node, including a nested one', () => {
    const store = loadSample()
    const subA1 = idByText(store, '子A1')
    const id = store.insertBraceMapChild(subA1, '孙A1', 0)
    expect(id).toBeTruthy()
    expect(childTexts(store, subA1)).toEqual(['孙A1'])
    expect(childTexts(store, idByText(store, '部分A'))).toEqual(['子A1', '子A2'])
  })
})
