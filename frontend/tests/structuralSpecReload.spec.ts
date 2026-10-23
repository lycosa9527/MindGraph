/**
 * A structure edit reloads the current diagram without looking like a new open.
 */
import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'
import { STRUCTURAL_SPEC_RELOAD } from '@/stores/diagram/types'

describe('structural diagram reloads', () => {
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

  it('keeps the session, theme, and step style when a flow step is added', () => {
    const store = useDiagramStore()
    expect(
      store.loadFromSpec(
        { title: 'Plan', steps: [{ id: 'step-keep', text: 'Start' }] },
        'flow_map',
        { emitLoaded: false }
      )
    ).toBe(true)
    store.sessionEditCount = 4
    if (store.data) store.data._mindmap_theme = 'ink'
    const step = store.data?.nodes.find((node) => node.id === 'step-keep')
    expect(step).toBeTruthy()
    if (step) step.style = { ...(step.style ?? {}), fontSize: 22 }
    store.layoutMeasureSettling = false

    expect(store.addFlowMapStep('Next')).toBe(true)

    expect(store.sessionEditCount).toBe(4)
    expect(store.layoutMeasureSettling).toBe(false)
    expect(store.data?._mindmap_theme).toBe('ink')
    expect(store.data?.nodes.find((node) => node.id === 'step-keep')?.style?.fontSize).toBe(22)
    expect(store.data?.nodes.some((node) => node.text === 'Next')).toBe(true)
    expect(store.history).toHaveLength(1)
    expect(store.history[0]?.action).toBe('Add flow step')
    expect(store.canUndo).toBe(false)
  })

  it('keeps a tree node id, style, and hidden answer across a structural reload', () => {
    const store = useDiagramStore()
    const spec = {
      root: {
        text: 'Topic',
        children: [
          {
            id: 'tree-cat-keep',
            text: 'Cat',
            children: [{ id: 'tree-leaf-keep', text: 'Leaf' }],
          },
        ],
      },
    }
    expect(store.loadFromSpec(spec, 'tree_map', { emitLoaded: false })).toBe(true)
    const category = store.data?.nodes.find((node) => node.id === 'tree-cat-keep')
    expect(category).toBeTruthy()
    if (category) {
      category.style = { fontSize: 18 }
      category.data = { ...(category.data ?? {}), hiddenAnswer: 'secret' }
    }
    store.sessionEditCount = 2
    store.layoutMeasureSettling = false

    expect(
      store.loadFromSpec(
        {
          root: {
            text: 'Topic',
            children: [
              {
                id: 'tree-cat-keep',
                text: 'Cat',
                children: [{ id: 'tree-leaf-keep', text: 'Leaf' }],
              },
              { text: 'New', children: [] },
            ],
          },
        },
        'tree_map',
        STRUCTURAL_SPEC_RELOAD
      )
    ).toBe(true)

    const kept = store.data?.nodes.find((node) => node.id === 'tree-cat-keep')
    expect(kept?.style?.fontSize).toBe(18)
    expect(kept?.data?.hiddenAnswer).toBe('secret')
    expect(store.sessionEditCount).toBe(2)
    expect(store.layoutMeasureSettling).toBe(false)
    expect(store.data?.nodes.some((node) => node.text === 'New')).toBe(true)
  })

  it('resets the session when a diagram is opened', () => {
    const store = useDiagramStore()
    store.loadFromSpec({ title: 'Plan', steps: ['Start'] }, 'flow_map', { emitLoaded: false })
    store.sessionEditCount = 4
    store.loadFromSpec({ title: 'Other', steps: ['A'] }, 'flow_map', { emitLoaded: false })
    expect(store.sessionEditCount).toBe(0)
  })
})
