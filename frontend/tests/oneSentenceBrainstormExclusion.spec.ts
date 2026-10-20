/**
 * 对话式修改 (one-sentence sheet) and thinking-map AI头脑风暴 (AI brainstorm)
 * are separate overlays. Opening either one closes the other.
 */
import { type EffectScope, effectScope } from 'vue'

import { createPinia, setActivePinia } from 'pinia'

import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore } from '@/stores/diagram'
import { usePanelsStore } from '@/stores/panels'

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, path: '/editor' }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

const doubleBubbleSpec = {
  left: '电场',
  right: '磁场',
  similarities: ['看不见摸不着'],
  leftDifferences: ['有正负极性'],
  rightDifferences: ['有方向'],
}

describe('one sentence and AI brainstorm exclusivity', () => {
  let scope: EffectScope
  let openTool: ReturnType<typeof useMindMapSideToolbarState>['openTool']
  let handleToolSelect: ReturnType<typeof useMindMapSideToolbarState>['handleToolSelect']
  let activeTool: ReturnType<typeof useMindMapSideToolbarState>['activeTool']

  beforeAll(() => {
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
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })
    setActivePinia(createPinia())
    scope = effectScope()
    scope.run(() => {
      const toolbar = useMindMapSideToolbarState()
      openTool = toolbar.openTool
      handleToolSelect = toolbar.handleToolSelect
      activeTool = toolbar.activeTool
    })
    const diagram = useDiagramStore()
    expect(diagram.loadFromSpec(doubleBubbleSpec, 'double_bubble_map', { emitLoaded: false })).toBe(
      true
    )
  })

  beforeEach(() => {
    activeTool.value = null
    usePanelsStore().closeDiagramBrainstorm()
  })

  afterAll(() => {
    scope.stop()
    vi.unstubAllGlobals()
  })

  it('closes 对话式修改 when the double-bubble brainstorm palette opens', () => {
    openTool('one_sentence')
    expect(activeTool.value).toBe('one_sentence')

    usePanelsStore().openDiagramBrainstorm()

    expect(usePanelsStore().diagramBrainstormPanel.isOpen).toBe(true)
    expect(activeTool.value).toBeNull()
  })

  it('closes the brainstorm palette when 对话式修改 opens', () => {
    const panels = usePanelsStore()
    panels.openDiagramBrainstorm()
    panels.setDiagramBrainstormSuggestions([{ id: 'sim-1', text: '看不见摸不着', type: 'similarity' }])
    expect(panels.diagramBrainstormPanel.isOpen).toBe(true)

    openTool('one_sentence')

    expect(activeTool.value).toBe('one_sentence')
    expect(panels.diagramBrainstormPanel.isOpen).toBe(false)
    expect(panels.diagramBrainstormPanel.suggestions).toEqual([
      { id: 'sim-1', text: '看不见摸不着', type: 'similarity' },
    ])
  })

  it('closes 对话式修改 when the thinking-map ribbon opens brainstorm', () => {
    openTool('one_sentence')
    expect(activeTool.value).toBe('one_sentence')

    const panels = usePanelsStore()
    const owner = 'oneSentenceBrainstormExclusion.spec'
    eventBus.onWithOwner(
      'panel:open_requested',
      (data) => {
        if (data.panel === 'diagramBrainstorm') {
          panels.openDiagramBrainstorm()
        }
      },
      owner
    )
    try {
      handleToolSelect('waterfall')
      expect(panels.diagramBrainstormPanel.isOpen).toBe(true)
      expect(activeTool.value).toBeNull()
    } finally {
      eventBus.removeAllListenersForOwner(owner)
    }
  })
})
