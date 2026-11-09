import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { MIND_MAP_GEOMETRY, mindMapNodeHorizontalExtra } from '@/config/mindMapGeometry'
import { useDiagramStore } from '@/stores/diagram'
import { nodesWithMindMapWrapBoxes } from '@/stores/diagram/mindMapTextEditSize'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { loadMindMapSpec } from '@/stores/specLoader/mindMap'
import {
  estimateNodeWidthForCanvasMode,
  estimateTopicNodeWidthForCanvasMode,
  measureBranchNodeHeightForCanvasMode,
  measureMindMapUnderlineBoxMetrics,
} from '@/stores/specLoader/mindMapMeasurements'
import { useUIStore } from '@/stores/ui'
import type { DiagramData, DiagramNode } from '@/types'
import { createMindMapBranchPaintIndex, mindMapBranchPaintBox } from '@/utils/mindMapBranchPaintBox'

// jsdom has no layout: a label measures 0px, so every shape clamps to the min width.
// Shape tests turn on a one-em-per-character width.
const textWidthStub = vi.hoisted(() => ({ enabled: false }))
vi.mock('@/stores/specLoader/textMeasurement', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/stores/specLoader/textMeasurement')>()
  return {
    ...actual,
    measureTextWidth: (...args: Parameters<typeof actual.measureTextWidth>) =>
      textWidthStub.enabled
        ? (args[0] || '').trim().length * args[1]
        : actual.measureTextWidth(...args),
  }
})

function enableMindMapV2Canvas(): void {
  const flagsStore = useFeatureFlagsStore()
  flagsStore.flags = {
    external_base_url: '',
    feature_showcase: false,
    feature_knowledge_space: false,
    feature_library: false,
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
    textWidthStub.enabled = false
  })

  it('oval branch width includes the extra horizontal padding vs rounded/rectangle', () => {
    const text = '分支标题'
    const rounded = estimateNodeWidthForCanvasMode(text, 'branch-r-1-0', 'v2', 'rounded')
    const rectangle = estimateNodeWidthForCanvasMode(text, 'branch-r-1-0', 'v2', 'rectangle')
    const oval = estimateNodeWidthForCanvasMode(text, 'branch-r-1-0', 'v2', 'oval')
    const padDelta = mindMapNodeHorizontalExtra('oval') - mindMapNodeHorizontalExtra('rounded')

    expect(rectangle).toBe(rounded)
    expect(oval).toBe(rounded + padDelta)
    expect(padDelta).toBe(12)
  })

  it('oval topic width includes the extra horizontal padding', () => {
    textWidthStub.enabled = true
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
    textWidthStub.enabled = true
    const classic = loadMindMapSpec({
      topic: '中心主题内容',
      _mindmap_diagram_style: 'classic',
      children: [{ text: '一级分支内容', children: [{ text: '二级' }] }],
    })
    const bubble = loadMindMapSpec({
      topic: '中心主题内容',
      _mindmap_diagram_style: 'bubble',
      children: [{ text: '一级分支内容', children: [{ text: '二级' }] }],
    })

    const classicTopic = classic.nodes.find((n) => n.id === 'topic')
    const bubbleTopic = bubble.nodes.find((n) => n.id === 'topic')
    const classicL1 = classic.nodes.find((n) => n.text === '一级分支内容')
    const bubbleL1 = bubble.nodes.find((n) => n.text === '一级分支内容')
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

  it('replaces a stale collapsed L2 width with the one-line wrap box', () => {
    const node: DiagramNode = {
      id: 'branch-l-2-0',
      type: 'branch',
      text: '基因编辑技术迭代迅速，推广模式不断创新',
      position: { x: 0, y: 0 },
      data: { estimatedWidth: 184, estimatedHeight: 73 },
    }
    const data = {
      type: 'mindmap',
      nodes: [node],
      connections: [],
    } as DiagramData
    const stamped = nodesWithMindMapWrapBoxes([node], data)[0]
    expect(stamped?.data?.estimatedWidth).toBeGreaterThan(220)
    expect(stamped?.data?.estimatedHeight).toBeLessThan(50)
  })

  it('keeps the stored wrap box on a later layout pass', () => {
    const node: DiagramNode = {
      id: 'branch-l-2-0',
      type: 'branch',
      text: '国际监管模式差异与贸易影响',
      position: { x: -140.5, y: 10 },
      data: { estimatedWidth: 235, estimatedHeight: 30 },
    }
    const stamped = nodesWithMindMapWrapBoxes(
      [node],
      { type: 'mindmap', nodes: [node], connections: [] } as DiagramData,
      { reuseStored: true }
    )[0]
    expect(stamped).toBe(node)
  })

  it('keeps a stored wrap box when the browser measure is missing', () => {
    const original = navigator.userAgent
    Object.defineProperty(navigator, 'userAgent', {
      configurable: true,
      value: 'Mozilla/5.0 Chrome',
    })
    try {
      const node: DiagramNode = {
        id: 'leaf',
        type: 'branch',
        text: '国际监管',
        position: { x: -140.5, y: 10 },
        data: { estimatedWidth: 235, estimatedHeight: 32 },
      }
      const stamped = nodesWithMindMapWrapBoxes([node], {
        type: 'mindmap',
        nodes: [node],
        connections: [],
      } as DiagramData)[0]
      expect(stamped).toBe(node)
    } finally {
      Object.defineProperty(navigator, 'userAgent', {
        configurable: true,
        value: original,
      })
    }
  })

  it('measures a classic uuid leaf at the painted 14px underline box', () => {
    const text = '基因工程与合成生物学跨界融合创新'
    const leaf: DiagramNode = {
      id: 'leaf',
      type: 'branch',
      text,
      position: { x: 0, y: 0 },
    }
    const longer: DiagramNode = {
      id: 'longer',
      type: 'branch',
      text: `${text}增`,
      position: { x: 0, y: 0 },
    }
    const data = {
      type: 'mindmap',
      _mindmap_diagram_style: 'classic',
      nodes: [leaf, longer],
      connections: [
        { id: 'c0', source: 'topic', target: 'parent' },
        { id: 'c1', source: 'parent', target: 'leaf' },
        { id: 'c2', source: 'parent', target: 'longer' },
      ],
    } as DiagramData
    const stamped = nodesWithMindMapWrapBoxes([leaf, longer], data)
    const leafWidth = stamped[0]?.data?.estimatedWidth as number
    const longerWidth = stamped[1]?.data?.estimatedWidth as number
    // 16 Han at the painted 14px size, plus underline padding and no border.
    expect(leafWidth).toBe(16 * 14 + 24)
    expect(longerWidth - leafWidth).toBe(14)
  })

  it('restacks a saved mind map from the wrap box on open', () => {
    const longText = '基因编辑技术迭代迅速，推广模式不断创新'
    const shortText = '公众认知'
    const spec = {
      type: 'mindmap',
      _mindmap_diagram_style: 'classic',
      nodes: [
        {
          id: 'topic',
          type: 'topic',
          text: '主题',
          position: { x: 400, y: 200 },
          data: { estimatedWidth: 120, estimatedHeight: 48 },
        },
        {
          id: 'branch-l-1-0',
          type: 'branch',
          text: '有趣点',
          position: { x: 200, y: 200 },
          data: { estimatedWidth: 90, estimatedHeight: 36 },
        },
        {
          id: 'branch-l-2-0',
          type: 'branch',
          text: longText,
          position: { x: -195, y: 160 },
          data: { estimatedWidth: 184, estimatedHeight: 73 },
        },
        {
          id: 'branch-l-2-1',
          type: 'branch',
          text: shortText,
          position: { x: -167, y: 200 },
          data: { estimatedWidth: 299, estimatedHeight: 30 },
        },
      ],
      connections: [
        { id: 'c0', source: 'topic', target: 'branch-l-1-0' },
        { id: 'c1', source: 'branch-l-1-0', target: 'branch-l-2-0' },
        { id: 'c2', source: 'branch-l-1-0', target: 'branch-l-2-1' },
      ],
    }
    const store = useDiagramStore()
    expect(store.loadFromSpec(spec, 'mindmap', { emitLoaded: false })).toBe(true)
    const nodes = store.data?.nodes ?? []
    const longNode = nodes.find((node) => node.text === longText)
    const shortNode = nodes.find((node) => node.text === shortText)
    const longWidth = longNode?.data?.estimatedWidth as number
    const shortWidth = shortNode?.data?.estimatedWidth as number
    expect(longWidth).toBeGreaterThan(220)
    expect(longNode?.data?.estimatedHeight).toBeLessThan(50)
    expect(longNode?.position && shortNode?.position).toBeTruthy()
    if (!longNode?.position || !shortNode?.position) return
    expect(longNode.position.x + longWidth).toBeCloseTo(shortNode.position.x + shortWidth, 0)
    expect(longNode.position.x).not.toBe(-195)
  })
})

describe('mindMapBranchPaintBox', () => {
  it('does not treat a uuid with no parent as level 1', () => {
    const box = mindMapBranchPaintBox({ id: '8f3c2a1b-leaf', type: 'branch' }, [], 'classic')
    expect(box.depth).toBe(2)
    expect(box.fontSize).toBe(MIND_MAP_GEOMETRY.fontSize)
    expect(box.shape).toBe('underline')
    expect(box.horizontalExtra).toBe(MIND_MAP_GEOMETRY.paddingX * 2)
  })

  it('uses one depth walk for a parent and its child', () => {
    const connections = [
      { source: 'topic', target: 'interest' },
      { source: 'interest', target: 'leaf' },
    ]
    const paintOf = createMindMapBranchPaintIndex(connections, 'classic')
    const parent = paintOf({ id: 'interest', type: 'branch' })
    const leaf = paintOf({ id: 'leaf', type: 'branch' })
    expect(parent).toMatchObject({
      depth: 1,
      fontSize: MIND_MAP_GEOMETRY.branchFontSize,
      shape: 'rounded',
    })
    expect(leaf).toMatchObject({
      depth: 2,
      fontSize: MIND_MAP_GEOMETRY.fontSize,
      shape: 'underline',
      horizontalExtra: MIND_MAP_GEOMETRY.paddingX * 2,
    })
    expect(mindMapBranchPaintBox({ id: 'leaf', type: 'branch' }, connections, 'classic')).toEqual(
      leaf
    )
  })
})
