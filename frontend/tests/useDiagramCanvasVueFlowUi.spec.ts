import { ref } from 'vue'

import { afterEach, describe, expect, it } from 'vitest'

import { useDiagramCanvasVueFlowUi } from '@/composables/diagramCanvas/useDiagramCanvasVueFlowUi'
import { learningSheetPickActive } from '@/composables/mindMap/useLearningSheetCustomMode'
import { MINDGRAPH_HEADLESS_EXPORT_KEY } from '@/utils/headlessExportSession'

function buildUiOptions(overrides: Partial<Parameters<typeof useDiagramCanvasVueFlowUi>[0]> = {}) {
  return {
    diagramStore: {
      type: 'mindmap',
    } as ReturnType<typeof import('@/stores').useDiagramStore>,
    presentationRailOpen: ref(false),
    handToolActive: ref(false),
    presentationPointerEditMode: ref(false),
    presentationHandPanMode: ref(false),
    browseMode: ref(false),
    panOnDragButtons: ref<number[] | null>(null),
    enableTouchPanPinch: ref(false),
    presentationTool: ref<'pointer' | 'highlighter' | 'pen' | 'timer'>('pointer'),
    presentationHighlighterColor: ref('#fef08a'),
    presentationPenColor: ref('#ef4444'),
    ...overrides,
  }
}

describe('useDiagramCanvasVueFlowUi', () => {
  it('box-selects only while Control is held so a plain left-drag can slash', () => {
    learningSheetPickActive.value = false
    const ui = useDiagramCanvasVueFlowUi(buildUiOptions())
    expect(ui.selectNodesOnDrag.value).toBe(true)
    expect(ui.selectionKeyCode.value).toBe('Control')
    expect(ui.effectivePanOnDrag.value).toEqual([1])
    expect(ui.elementsSelectable.value).toBe(true)
  })

  it('disables marquee and VF pan when mobile panOnDragButtons are set', () => {
    learningSheetPickActive.value = false
    const ui = useDiagramCanvasVueFlowUi(
      buildUiOptions({
        panOnDragButtons: ref<number[] | null>([0, 1, 2]),
      })
    )
    expect(ui.selectNodesOnDrag.value).toBe(false)
    expect(ui.selectionKeyCode.value).toBe(null)
    expect(ui.effectivePanOnDrag.value).toBe(false)
    // Tap-to-select nodes must still work
    expect(ui.elementsSelectable.value).toBe(true)
  })

  it('e-blackboard keeps middle-button pan and Ctrl box-select, not drag-select', () => {
    learningSheetPickActive.value = false
    const ui = useDiagramCanvasVueFlowUi(
      buildUiOptions({
        enableTouchPanPinch: ref(true),
      })
    )
    expect(ui.selectNodesOnDrag.value).toBe(false)
    // A finger cannot hold Control, so the slash stays the default drag.
    expect(ui.selectionKeyCode.value).toBe('Control')
    expect(ui.effectivePanOnDrag.value).toEqual([1])
    expect(ui.elementsSelectable.value).toBe(true)
  })

  it('turns box select off while a learning sheet is being picked', () => {
    learningSheetPickActive.value = true
    const ui = useDiagramCanvasVueFlowUi(buildUiOptions())
    expect(ui.selectNodesOnDrag.value).toBe(false)
    expect(ui.selectionKeyCode.value).toBe(null)
  })

  it('browse mode selects on click, pans on drag, and skips marquee', () => {
    learningSheetPickActive.value = false
    const ui = useDiagramCanvasVueFlowUi(
      buildUiOptions({
        diagramStore: { type: 'bubble_map' } as ReturnType<
          typeof import('@/stores').useDiagramStore
        >,
        browseMode: ref(true),
        handToolActive: ref(true),
      })
    )
    expect(ui.effectivePanOnDrag.value).toEqual([0, 1, 2])
    expect(ui.elementsSelectable.value).toBe(true)
    expect(ui.selectNodesOnDrag.value).toBe(false)
    expect(ui.selectionKeyCode.value).toBe(null)
    expect(ui.nodesDraggable.value).toBe(false)
  })

  it('hand tool pans with all buttons and turns selection off', () => {
    learningSheetPickActive.value = false
    const ui = useDiagramCanvasVueFlowUi(
      buildUiOptions({
        handToolActive: ref(true),
      })
    )
    expect(ui.effectivePanOnDrag.value).toEqual([0, 1, 2])
    expect(ui.selectNodesOnDrag.value).toBe(false)
    expect(ui.selectionKeyCode.value).toBe(null)
    expect(ui.elementsSelectable.value).toBe(false)
  })

  afterEach(() => {
    sessionStorage.removeItem(MINDGRAPH_HEADLESS_EXPORT_KEY)
  })

  it('disables node selection during headless export screenshots', () => {
    learningSheetPickActive.value = false
    sessionStorage.setItem(MINDGRAPH_HEADLESS_EXPORT_KEY, '1')
    const ui = useDiagramCanvasVueFlowUi(buildUiOptions())
    expect(ui.elementsSelectable.value).toBe(false)
  })
})
