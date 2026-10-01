import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  handleLearningSheetPickNodeClick,
  learningSheetPickActive,
} from '@/composables/mindMap/useLearningSheetCustomMode'
import { useDiagramStore } from '@/stores/diagram'
import { LEARNING_SHEET_BLANK_TEXT } from '@/stores/specLoader/utils'

describe('learning sheet mind-map layout hold', () => {
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

  function loadBranch(): { branchId: string } {
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('mindmap')
    const branch = diagramStore.data?.nodes.find(
      (node) => node.type === 'branch' && String(node.text ?? '').trim().length > 0
    )
    if (!branch) throw new Error('expected a branch node')
    return { branchId: branch.id }
  }

  it('keeps the measured box when a custom blank would otherwise grow from the text estimate', () => {
    const diagramStore = useDiagramStore()
    const { branchId } = loadBranch()
    const measuredWidth = 180
    const measuredHeight = 36
    diagramStore.mindMapNodeWidths[branchId] = measuredWidth
    diagramStore.mindMapNodeHeights[branchId] = measuredHeight
    const node = diagramStore.data?.nodes.find((item) => item.id === branchId)
    if (node) {
      node.data = {
        ...(node.data as Record<string, unknown>),
        estimatedWidth: 900,
        estimatedHeight: 120,
      }
    }
    const positionsBefore = (diagramStore.data?.nodes ?? []).map((item) => ({
      id: item.id,
      x: item.position?.x,
      y: item.position?.y,
    }))
    const triggerBefore = diagramStore.mindMapRecalcTrigger

    diagramStore.setLearningSheetMode(true)
    learningSheetPickActive.value = true
    handleLearningSheetPickNodeClick(branchId)

    const blanked = diagramStore.data?.nodes.find((item) => item.id === branchId)
    expect(blanked?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
    expect(diagramStore.mindMapNodeWidths[branchId]).toBe(measuredWidth)
    expect(diagramStore.mindMapNodeHeights[branchId]).toBe(measuredHeight)
    expect((blanked?.data as { estimatedWidth?: number }).estimatedWidth).toBe(measuredWidth)
    expect((blanked?.data as { estimatedHeight?: number }).estimatedHeight).toBe(measuredHeight)
    expect(diagramStore.mindMapRecalcTrigger).toBe(triggerBefore)
    for (const before of positionsBefore) {
      const item = diagramStore.data?.nodes.find((node) => node.id === before.id)
      expect(item?.position?.x).toBe(before.x)
      expect(item?.position?.y).toBe(before.y)
    }
  })
})
