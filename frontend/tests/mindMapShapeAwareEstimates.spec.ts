import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mindMapNodeHorizontalExtra } from '@/config/mindMapGeometry'
import { loadMindMapSpec } from '@/stores/specLoader/mindMap'
import {
  estimateNodeWidthForCanvasMode,
  estimateTopicNodeWidthForCanvasMode,
  measureBranchNodeHeightForCanvasMode,
  measureMindMapUnderlineBoxMetrics,
} from '@/stores/specLoader/mindMapMeasurements'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'

function enableMindMapV2Canvas(): void {
  const flagsStore = useFeatureFlagsStore()
  flagsStore.flags = {
    external_base_url: '',
    feature_rag_chunk_test: false,
    feature_course: false,
    feature_template: false,
    feature_community: false,
    feature_showcase: false,
    feature_askonce: true,
    feature_debateverse: false,
    feature_knowledge_space: false,
    feature_mindmap_v2_canvas: true,
    feature_library: false,
    feature_gewe: false,
    feature_smart_response: false,
    feature_teacher_usage: false,
    feature_workshop_chat: false,
    feature_markets: false,
    feature_mindbot: false,
    feature_mindmate_export: false,
    feature_kitty_agent: false,
    feature_auth_pixel_battle: false,
    feature_test_server_banner: false,
    feature_thinking_coins: false,
    workshop_chat_preview_org_ids: [],
    feature_org_access: {},
  }
  useUIStore().mindMapCanvasMode = 'v2'
}

describe('mind-map shape-aware size estimates', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      length: 0,
      key: vi.fn(() => null),
    })
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        onchange: null,
        addListener: vi.fn(),
        addEventListener: vi.fn(),
        removeListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    enableMindMapV2Canvas()
  })

  it('oval branch width includes the extra horizontal padding vs rounded/rectangle', () => {
    const text = '分支标题'
    const rounded = estimateNodeWidthForCanvasMode(text, 'branch-r-1-0', 'v2', 'rounded')
    const rectangle = estimateNodeWidthForCanvasMode(text, 'branch-r-1-0', 'v2', 'rectangle')
    const oval = estimateNodeWidthForCanvasMode(text, 'branch-r-1-0', 'v2', 'oval')
    const padDelta =
      mindMapNodeHorizontalExtra('oval') - mindMapNodeHorizontalExtra('rounded')

    expect(rectangle).toBe(rounded)
    expect(oval).toBe(rounded + padDelta)
    expect(padDelta).toBe(12)
  })

  it('oval topic width includes the extra horizontal padding', () => {
    const text = '中心主题'
    const rect = estimateTopicNodeWidthForCanvasMode(text, 'v2', 'rectangle')
    const oval = estimateTopicNodeWidthForCanvasMode(text, 'v2', 'oval')
    expect(oval).toBe(
      rect + (mindMapNodeHorizontalExtra('oval') - mindMapNodeHorizontalExtra('rectangle'))
    )
  })

  it('underline branch height is shorter than box shapes', () => {
    const text = '二级节点'
    const boxH = measureBranchNodeHeightForCanvasMode(text, 'branch-r-2-0', 'v2')
    const underlineH = measureMindMapUnderlineBoxMetrics(text, 'branch-r-2-0').totalHeight
    expect(underlineH).toBeLessThan(boxH)
  })

  it('bubble style load stamps oval widths on topic and L1 (not rounded padding)', () => {
    const classic = loadMindMapSpec({
      topic: '主题',
      _mindmap_diagram_style: 'classic',
      children: [{ text: '一级', children: [{ text: '二级' }] }],
    })
    const bubble = loadMindMapSpec({
      topic: '主题',
      _mindmap_diagram_style: 'bubble',
      children: [{ text: '一级', children: [{ text: '二级' }] }],
    })

    const classicTopic = classic.nodes.find((n) => n.id === 'topic')
    const bubbleTopic = bubble.nodes.find((n) => n.id === 'topic')
    const classicL1 = classic.nodes.find((n) => n.text === '一级')
    const bubbleL1 = bubble.nodes.find((n) => n.text === '一级')
    const classicL2 = classic.nodes.find((n) => n.text === '二级')
    const bubbleL2 = bubble.nodes.find((n) => n.text === '二级')

    expect(bubbleTopic?.style?.nodeShape).toBe('oval')
    expect(bubbleL1?.style?.nodeShape).toBe('oval')
    expect(bubbleL2?.style?.nodeShape).toBe('underline')

    expect(bubbleTopic?.data?.estimatedWidth).toBeGreaterThan(
      classicTopic?.data?.estimatedWidth as number
    )
    expect(bubbleL1?.data?.estimatedWidth).toBeGreaterThan(
      classicL1?.data?.estimatedWidth as number
    )
    // L2 underline in both classic and bubble — same height regime
    expect(bubbleL2?.data?.estimatedHeight).toBe(classicL2?.data?.estimatedHeight)
  })

  it('formal style uses taller box heights for L2 than classic underline L2', () => {
    const classic = loadMindMapSpec({
      topic: '主题',
      _mindmap_diagram_style: 'classic',
      children: [{ text: '一级', children: [{ text: '二级节点' }] }],
    })
    const formal = loadMindMapSpec({
      topic: '主题',
      _mindmap_diagram_style: 'formal',
      children: [{ text: '一级', children: [{ text: '二级节点' }] }],
    })

    const classicL2 = classic.nodes.find((n) => n.text === '二级节点')
    const formalL2 = formal.nodes.find((n) => n.text === '二级节点')
    expect(formalL2?.style?.nodeShape).toBe('rectangle')
    expect(classicL2?.style?.nodeShape).toBe('underline')
    expect(formalL2?.data?.estimatedHeight as number).toBeGreaterThan(
      classicL2?.data?.estimatedHeight as number
    )
  })
})
