import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { usePanelsStore } from '@/stores/panels'

describe('panels store overlay exclusivity', () => {
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
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('closes AI brainstorm when conversational edit opens', () => {
    const panels = usePanelsStore()
    panels.openAiBrainstorm()
    expect(panels.aiBrainstormPanel.isOpen).toBe(true)

    panels.openMindmate()
    expect(panels.mindmatePanel.isOpen).toBe(true)
    expect(panels.aiBrainstormPanel.isOpen).toBe(false)
  })

  it('closes conversational edit when AI brainstorm opens', () => {
    const panels = usePanelsStore()
    panels.openMindmate()
    expect(panels.mindmatePanel.isOpen).toBe(true)

    panels.openAiBrainstorm()
    expect(panels.aiBrainstormPanel.isOpen).toBe(true)
    expect(panels.mindmatePanel.isOpen).toBe(false)
  })

  it('closes node palette brainstorm when conversational edit opens', () => {
    const panels = usePanelsStore()
    panels.openNodePalette()
    expect(panels.nodePalettePanel.isOpen).toBe(true)

    panels.openMindmate()
    expect(panels.mindmatePanel.isOpen).toBe(true)
    expect(panels.nodePalettePanel.isOpen).toBe(false)
  })

  it('closes conversational edit when node palette brainstorm opens', () => {
    const panels = usePanelsStore()
    panels.openMindmate()
    expect(panels.mindmatePanel.isOpen).toBe(true)

    panels.openNodePalette()
    expect(panels.nodePalettePanel.isOpen).toBe(true)
    expect(panels.mindmatePanel.isOpen).toBe(false)
  })

  it('keeps live AI brainstorm suggestions after a conversational-edit round trip', () => {
    const panels = usePanelsStore()
    const stale = { id: 's-stale', text: 'older', type: 'branch' }
    const live = { id: 's-live', text: 'newer', type: 'branch' }
    const diagramKey = 'ai-brainstorm-mindmap-1'

    panels.openAiBrainstorm({ diagramKey })
    panels.setAiBrainstormSuggestions([stale])
    panels.saveAiBrainstormSession(diagramKey)
    panels.setAiBrainstormSuggestions([live])

    panels.openMindmate()
    expect(panels.aiBrainstormPanel.isOpen).toBe(false)
    expect(panels.aiBrainstormPanel.suggestions).toEqual([live])

    panels.openAiBrainstorm({ diagramKey })
    expect(panels.aiBrainstormPanel.isOpen).toBe(true)
    expect(panels.mindmatePanel.isOpen).toBe(false)
    expect(panels.aiBrainstormPanel.suggestions).toEqual([live])
  })

  it('toggles conversational edit through the exclusive open path', () => {
    const panels = usePanelsStore()
    panels.openAiBrainstorm()
    panels.toggleMindmatePanel()
    expect(panels.mindmatePanel.isOpen).toBe(true)
    expect(panels.aiBrainstormPanel.isOpen).toBe(false)

    panels.toggleMindmatePanel()
    expect(panels.mindmatePanel.isOpen).toBe(false)
  })
})
