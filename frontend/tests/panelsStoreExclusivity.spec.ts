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

  it('closes AI brainstorm brainstorm when conversational edit opens', () => {
    const panels = usePanelsStore()
    panels.openDiagramBrainstorm()
    expect(panels.diagramBrainstormPanel.isOpen).toBe(true)

    panels.openMindmate()
    expect(panels.mindmatePanel.isOpen).toBe(true)
    expect(panels.diagramBrainstormPanel.isOpen).toBe(false)
  })

  it('closes conversational edit when AI brainstorm brainstorm opens', () => {
    const panels = usePanelsStore()
    panels.openMindmate()
    expect(panels.mindmatePanel.isOpen).toBe(true)

    panels.openDiagramBrainstorm()
    expect(panels.diagramBrainstormPanel.isOpen).toBe(true)
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

  it('keeps thinking-map brainstorm separate from the mind-map sheet', () => {
    const panels = usePanelsStore()
    panels.openAiBrainstorm()
    panels.setAiBrainstormSuggestions([{ id: 'mind', text: 'branch', type: 'branch' }])

    panels.openDiagramBrainstorm()
    expect(panels.diagramBrainstormPanel.isOpen).toBe(true)
    expect(panels.aiBrainstormPanel.isOpen).toBe(false)
    expect(panels.diagramBrainstormPanel.suggestions).toEqual([])
    expect(panels.aiBrainstormPanel.suggestions).toEqual([
      { id: 'mind', text: 'branch', type: 'branch' },
    ])

    panels.setDiagramBrainstormSuggestions([{ id: 'think', text: 'idea', type: 'context' }])
    panels.openAiBrainstorm()
    expect(panels.aiBrainstormPanel.isOpen).toBe(true)
    expect(panels.diagramBrainstormPanel.isOpen).toBe(false)
    expect(panels.diagramBrainstormPanel.suggestions).toEqual([
      { id: 'think', text: 'idea', type: 'context' },
    ])
    expect(panels.openPanelCount).toBe(1)
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
