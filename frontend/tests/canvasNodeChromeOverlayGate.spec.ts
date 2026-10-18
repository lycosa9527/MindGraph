import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it } from 'vitest'

import { pushCanvasCoveringOverlay } from '@/components/common/swissGlassStack'
import {
  canvasNodeChromeBlockedByOverlay,
  useCanvasNodeChromeOverlayGate,
} from '@/composables/canvasToolbar/canvasNodeChromeOverlayGate'
import {
  isCoveringMindMapSideTool,
  resetMindMapSideToolbarState,
} from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { usePanelsStore } from '@/stores/panels'

describe('canvasNodeChromeOverlayGate', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    resetMindMapSideToolbarState()
  })

  it('reacts when a registered body overlay or parking lot opens', () => {
    const panels = usePanelsStore()
    const blocked = useCanvasNodeChromeOverlayGate()
    expect(blocked.value).toBe(false)
    const release = pushCanvasCoveringOverlay()
    try {
      expect(blocked.value).toBe(true)
    } finally {
      release()
    }
    expect(blocked.value).toBe(false)
    panels.updateNodePalette({ open: true })
    expect(blocked.value).toBe(true)
    panels.updateAiBrainstorm({ open: true })
    expect(blocked.value).toBe(true)
  })

  it('treats brainstorm, parking lot, and body dialogs as covering', () => {
    expect(
      canvasNodeChromeBlockedByOverlay({
        nodePaletteOpen: false,
        aiBrainstormOpen: false,
        coveringSideTool: false,
        coveringDialogOpen: false,
      })
    ).toBe(false)
    expect(
      canvasNodeChromeBlockedByOverlay({
        nodePaletteOpen: true,
        aiBrainstormOpen: false,
        coveringSideTool: false,
        coveringDialogOpen: false,
      })
    ).toBe(true)
    expect(
      canvasNodeChromeBlockedByOverlay({
        nodePaletteOpen: false,
        aiBrainstormOpen: true,
        coveringSideTool: false,
        coveringDialogOpen: false,
      })
    ).toBe(true)
    expect(
      canvasNodeChromeBlockedByOverlay({
        nodePaletteOpen: false,
        aiBrainstormOpen: false,
        coveringSideTool: true,
        coveringDialogOpen: false,
      })
    ).toBe(true)
    expect(
      canvasNodeChromeBlockedByOverlay({
        nodePaletteOpen: false,
        aiBrainstormOpen: false,
        coveringSideTool: false,
        coveringDialogOpen: true,
      })
    ).toBe(true)
  })

  it('hides chrome for modal side tools but not the outline rail', () => {
    expect(isCoveringMindMapSideTool('waterfall')).toBe(true)
    expect(isCoveringMindMapSideTool('document_summary')).toBe(true)
    expect(isCoveringMindMapSideTool('one_sentence')).toBe(true)
    expect(isCoveringMindMapSideTool('learning_sheet')).toBe(true)
    expect(isCoveringMindMapSideTool('outline')).toBe(false)
    expect(isCoveringMindMapSideTool(null)).toBe(false)
  })
})
