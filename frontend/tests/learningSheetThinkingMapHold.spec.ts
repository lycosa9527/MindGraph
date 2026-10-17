import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'
import { mergeReloadedNodeFields } from '@/stores/diagram/structuralSpecReload'
import { recalculateBubbleMapLayout } from '@/stores/specLoader/bubbleMap'
import { recalculateCircleMapLayout } from '@/stores/specLoader/circleMap'
import { LEARNING_SHEET_BLANK_TEXT } from '@/stores/specLoader/utils'
import type { DiagramNode } from '@/types'
import { isBubbleMapAttributeNode } from '@/utils/bubbleMapIdentity'
import { isCircleMapContextNode } from '@/utils/circleMapIdentity'
import { isDoubleBubbleRoleNode } from '@/utils/doubleBubbleMapIdentity'

const LONG_LABEL = 'photosynthesis inside the leaf chloroplast during daylight'

describe('thinking map learning sheet hold', () => {
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

  function blankable(
    nodes: DiagramNode[] | undefined,
    pred: (node: DiagramNode) => boolean
  ): DiagramNode {
    const node = nodes?.find((item) => pred(item) && String(item.text ?? '').trim().length > 0)
    if (!node) throw new Error('expected a blankable node')
    return node
  }

  it('keeps circle-map context size and positions when a node is blanked', () => {
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('circle_map')
    const context = blankable(diagramStore.data?.nodes, isCircleMapContextNode)
    diagramStore.updateNode(context.id, { text: LONG_LABEL })

    const before = recalculateCircleMapLayout(diagramStore.data?.nodes ?? [], {})
    const beforeContext = before.find((node) => node.id === context.id)
    const sizeBefore = beforeContext?.style?.size

    diagramStore.setLearningSheetMode(true)
    expect(diagramStore.emptyNodeForLearningSheet(context.id)).toBe(true)

    const after = recalculateCircleMapLayout(diagramStore.data?.nodes ?? [], {})
    const afterContext = after.find((node) => node.id === context.id)
    expect(afterContext?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
    expect(afterContext?.style?.size).toBe(sizeBefore)
    expect(sizeBefore).toBeGreaterThan(40)

    for (const node of before) {
      const next = after.find((item) => item.id === node.id)
      expect(next?.position?.x).toBe(node.position?.x)
      expect(next?.position?.y).toBe(node.position?.y)
    }
  })

  it('keeps bubble-map attribute radius when a node is blanked', () => {
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('bubble_map')
    const attribute = blankable(diagramStore.data?.nodes, isBubbleMapAttributeNode)
    diagramStore.updateNode(attribute.id, { text: LONG_LABEL })

    const before = recalculateBubbleMapLayout(diagramStore.data?.nodes ?? [], {})
    const sizeBefore = before.find((node) => node.id === attribute.id)?.style?.size

    diagramStore.setLearningSheetMode(true)
    expect(diagramStore.emptyNodeForLearningSheet(attribute.id)).toBe(true)

    const after = recalculateBubbleMapLayout(diagramStore.data?.nodes ?? [], {})
    const blanked = after.find((node) => node.id === attribute.id)
    expect(blanked?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
    expect(blanked?.style?.size).toBe(sizeBefore)
  })

  it('ignores a smaller measurement while the node stays blanked', () => {
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('circle_map')
    const context = blankable(diagramStore.data?.nodes, isCircleMapContextNode)
    diagramStore.setNodeDimensions(context.id, 160, 160)
    diagramStore.setLearningSheetMode(true)
    expect(diagramStore.emptyNodeForLearningSheet(context.id)).toBe(true)

    diagramStore.setNodeDimensions(context.id, 12, 12)

    expect(diagramStore.nodeDimensions[context.id]).toEqual({ width: 160, height: 160 })
    const held = diagramStore.data?.nodes.find((node) => node.id === context.id)
    expect((held?.data as { learningSheetHoldWidth?: number }).learningSheetHoldWidth).toBe(160)
  })

  it('rebuilds a double-bubble spec from the hidden answer', () => {
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('double_bubble_map')
    const similarity = blankable(diagramStore.data?.nodes, (node) =>
      isDoubleBubbleRoleNode(node, 'similarity')
    )
    const answer = String(similarity.text)
    diagramStore.setLearningSheetMode(true)
    expect(diagramStore.emptyNodeForLearningSheet(similarity.id)).toBe(true)

    const spec = diagramStore.getDoubleBubbleSpecFromData()
    const rows = spec?.similarities as Array<{ id?: string; text: string }>
    expect(rows.find((row) => row.id === similarity.id)?.text).toBe(answer)
  })

  it('keeps a blank when a structural reload merges the previous node', () => {
    const previous: DiagramNode[] = [
      {
        id: 'sim-1',
        text: '',
        type: 'bubble',
        data: {
          hidden: true,
          hiddenAnswer: 'water',
          learningSheetHoldWidth: 88,
          learningSheetHoldHeight: 36,
        },
      },
    ]
    const reloaded: DiagramNode[] = [
      {
        id: 'sim-1',
        text: 'water',
        type: 'bubble',
        data: {},
      },
    ]
    const merged = mergeReloadedNodeFields(reloaded, previous, true)
    expect(merged[0]?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
    expect((merged[0]?.data as { hidden?: boolean }).hidden).toBe(true)
    expect((merged[0]?.data as { hiddenAnswer?: string }).hiddenAnswer).toBe('water')
    expect((merged[0]?.data as { learningSheetHoldWidth?: number }).learningSheetHoldWidth).toBe(88)
  })
})
