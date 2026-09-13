import { describe, expect, it, vi } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import {
  MIND_MAP_SLIDE_TRANSITION_MS,
  emitMindMapSlideViewportFit,
} from '@/composables/mindMap/emitMindMapSlideViewportFit'

describe('emitMindMapSlideViewportFit', () => {
  it('fits the whole window for the overview slide', () => {
    const fitCanvas = vi.fn()
    const fitNodes = vi.fn()
    const stopCanvas = eventBus.on('view:fit_to_canvas_requested', fitCanvas)
    const stopNodes = eventBus.on('view:fit_to_nodes_requested', fitNodes)

    emitMindMapSlideViewportFit({
      kind: 'overview',
      focusNodeIds: ['root', 'a'],
    })

    expect(fitCanvas).toHaveBeenCalledWith(
      expect.objectContaining({ animate: true, userInitiated: true })
    )
    expect(fitNodes).not.toHaveBeenCalled()
    stopCanvas()
    stopNodes()
  })

  it('zooms to the branch nodes for a branch slide', () => {
    const fitCanvas = vi.fn()
    const fitNodes = vi.fn()
    const stopCanvas = eventBus.on('view:fit_to_canvas_requested', fitCanvas)
    const stopNodes = eventBus.on('view:fit_to_nodes_requested', fitNodes)

    emitMindMapSlideViewportFit({
      kind: 'branch',
      focusNodeIds: ['branch-1'],
    })

    expect(fitCanvas).not.toHaveBeenCalled()
    expect(fitNodes).toHaveBeenCalledWith(
      expect.objectContaining({
        nodeIds: ['branch-1'],
        animate: true,
        duration: MIND_MAP_SLIDE_TRANSITION_MS,
        padding: 0.45,
        userInitiated: true,
      })
    )
    stopCanvas()
    stopNodes()
  })
})
