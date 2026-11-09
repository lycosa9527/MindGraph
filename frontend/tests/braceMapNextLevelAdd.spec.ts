import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { createThinkingMapLevelAdds } from '@/composables/editor/thinkingMapLevelAdd'
import { diagramInsertLabel } from '@/diagramBilingual/insertLabel'
import { useDiagramStore } from '@/stores/diagram'
import { braceMapRootId } from '@/stores/diagram/braceMapParentResolve'
import { useUIStore } from '@/stores/ui'

type DiagramSession = ReturnType<typeof useDiagramSession>

function stubMatchMedia(): void {
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
}

function childIds(store: ReturnType<typeof useDiagramStore>, parentId: string): string[] {
  return (store.data?.connections ?? [])
    .filter((edge) => edge.source === parentId)
    .map((edge) => edge.target)
}

function setup() {
  useUIStore().language = 'en'
  const store = useDiagramStore()
  expect(store.loadDefaultTemplate('brace_map')).toBe(true)
  const notify = { success: vi.fn(), successKey: vi.fn(), warningKey: vi.fn() }
  const adds = createThinkingMapLevelAdds(
    store as unknown as DiagramSession,
    (key) => key,
    (key, named) => diagramInsertLabel(store.data?.languages, key, named),
    notify
  )
  const rootId = braceMapRootId(store.data?.nodes ?? [], store.data?.connections ?? []) ?? ''
  const firstPart = childIds(store, rootId).filter((id) => id !== 'dimension-label')[0]
  const firstSubpart = childIds(store, firstPart)[0]
  return { store, adds, notify, rootId, firstPart, firstSubpart }
}

describe('brace map next-level add', () => {
  beforeEach(() => {
    stubMatchMedia()
    setActivePinia(createPinia())
  })

  it('adds two children under a selected subpart that has none, then one more', () => {
    const { store, adds, firstSubpart } = setup()
    expect(firstSubpart).toBeTruthy()
    expect(childIds(store, firstSubpart)).toHaveLength(0)

    store.selectNodes(firstSubpart)
    expect(adds.addBraceNextLevelNode()).toBe(true)
    expect(childIds(store, firstSubpart)).toHaveLength(2)

    store.selectNodes(firstSubpart)
    expect(adds.addBraceNextLevelNode()).toBe(true)
    expect(childIds(store, firstSubpart)).toHaveLength(3)
  })

  it('attaches below a grandchild instead of snapping back to the part', () => {
    const { store, adds, firstPart, firstSubpart } = setup()
    store.selectNodes(firstSubpart)
    adds.addBraceNextLevelNode()
    const grandchild = childIds(store, firstSubpart)[0]
    const partChildren = childIds(store, firstPart).length

    store.selectNodes(grandchild)
    expect(adds.addBraceNextLevelNode()).toBe(true)
    expect(childIds(store, grandchild)).toHaveLength(2)
    expect(childIds(store, firstPart)).toHaveLength(partChildren)
  })

  it('falls back to the last subpart when nothing usable is selected', () => {
    const { store, adds, rootId } = setup()
    const parts = childIds(store, rootId).filter((id) => id !== 'dimension-label')
    const lastPartSubparts = childIds(store, parts[parts.length - 1])
    const lastSubpart = lastPartSubparts[lastPartSubparts.length - 1]

    store.selectNodes(rootId)
    expect(adds.addBraceNextLevelNode()).toBe(true)
    expect(childIds(store, lastSubpart)).toHaveLength(2)
  })
})
