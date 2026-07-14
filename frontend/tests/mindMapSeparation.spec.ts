import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import {
  resolveLegacyMindMapConnectionStrokeColor,
  syncLegacyMindMapConnectionStrokeColors,
  syncMindMapConnectionStrokeColorsForCanvasMode,
} from '@/config/mindMapGeometry'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import { LEGACY_MINDMAP_BRANCH_COLORS } from '@/config/mindMapLegacyColors'
import {
  hydrateMindMapCanvasStylesOnLoad,
  reconcileMindMapCanvasModeSwitch,
  sanitizeLegacyNodeStyle,
  snapshotMindMapCanvasBucket,
} from '@/stores/diagram/mindMapCanvasModeSwitch'
import { getEdgeTypeForDiagram } from '@/stores/diagram/events'
import { useMindMapOpsSlice } from '@/stores/diagram/mindMapOps'
import type { DiagramContext } from '@/stores/diagram/types'
import {
  buildClassicMindMapTopicHandlePositions,
  classicMindMapPillHandleInsetPx,
  classicMindMapSideHandleTopPercent,
  withClassicMindMapTopicSourceHandle,
} from '@/utils/classicMindMapTopicHandles'
import { loadMindMapSpec } from '@/stores/specLoader'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import type { Connection, DiagramData, DiagramNode } from '@/types'

function enableMindMapV2CanvasFlag(): void {
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
}

function makeMindMapCtx(data: DiagramData): DiagramContext {
  return {
    type: ref('mindmap'),
    data: ref(data),
    selectedNodes: ref([]),
    mindMapNodeWidths: ref({}),
    mindMapNodeHeights: ref({}),
    mindMapRecalcTrigger: ref(0),
    mindMapCurveExtentBaseline: ref(null),
    mindMapPendingEditNodeId: ref(null),
    pushHistory: vi.fn(),
    scheduleMindMapRecalc: vi.fn(),
  } as DiagramContext
}

describe('mind map classic vs v2 separation', () => {
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
    vi.stubGlobal('matchMedia', vi.fn(() => ({
      matches: false,
      media: '',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })))
  })

  it('uses curved edges for legacy mind maps', () => {
    expect(getEdgeTypeForDiagram('mind_map', 'legacy')).toBe('curved')
    expect(getEdgeTypeForDiagram('mindmap', 'legacy')).toBe('curved')
  })

  it('uses orthogonal edges for v2 mind maps', () => {
    expect(getEdgeTypeForDiagram('mind_map', 'v2')).toBe('mindmapOrthogonal')
    expect(getEdgeTypeForDiagram('mindmap', 'v2')).toBe('mindmapOrthogonal')
  })

  it('restores per-branch stroke colors for legacy connections', () => {
    const nodes: DiagramNode[] = [
      {
        id: 'branch-r-0-1',
        text: 'Branch',
        type: 'branch',
        data: { branchIndex: 2 },
      },
    ]
    const connection: Connection = {
      id: 'edge-topic-branch-r-0-1',
      source: 'topic',
      target: 'branch-r-0-1',
    }
    expect(resolveLegacyMindMapConnectionStrokeColor(connection, nodes)).toBe(
      getMindmapBranchColor(2, 'legacy').border
    )
  })

  it('walks the branch tree when branchIndex is missing on intermediate nodes', () => {
    const nodes: DiagramNode[] = [
      {
        id: 'branch-r-0-1',
        text: 'Root branch',
        type: 'branch',
        data: { branchIndex: 4 },
      },
      {
        id: 'branch-r-1-2',
        text: 'Child',
        type: 'branch',
      },
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'branch-r-0-1' },
      { id: 'e2', source: 'branch-r-0-1', target: 'branch-r-1-2' },
    ]
    expect(
      resolveLegacyMindMapConnectionStrokeColor(connections[1], nodes, connections)
    ).toBe(getMindmapBranchColor(4, 'legacy').border)
  })

  it('syncLegacyMindMapConnectionStrokeColors assigns palette colors per edge', () => {
    const nodes: DiagramNode[] = [
      {
        id: 'branch-r-0-0',
        text: 'A',
        type: 'branch',
        data: { branchIndex: 0 },
      },
      {
        id: 'branch-r-0-1',
        text: 'B',
        type: 'branch',
        data: { branchIndex: 1 },
      },
    ]
    const connections: Connection[] = [
      { id: 'e0', source: 'topic', target: 'branch-r-0-0', style: { strokeColor: '#000000' } },
      { id: 'e1', source: 'topic', target: 'branch-r-0-1', style: { strokeColor: '#000000' } },
    ]
    syncLegacyMindMapConnectionStrokeColors(connections, nodes)
    expect(connections[0].style?.strokeColor).toBe(getMindmapBranchColor(0, 'legacy').border)
    expect(connections[1].style?.strokeColor).toBe(getMindmapBranchColor(1, 'legacy').border)
  })

  it('syncMindMapConnectionStrokeColorsForCanvasMode unifies strokes in v2 mode', () => {
    const nodes: DiagramNode[] = [
      {
        id: 'topic',
        text: 'Topic',
        type: 'topic',
        style: { borderColor: '#2563eb' },
      },
      {
        id: 'branch-r-0-0',
        text: 'A',
        type: 'branch',
        data: { branchIndex: 0 },
      },
    ]
    const connections: Connection[] = [
      { id: 'e0', source: 'topic', target: 'branch-r-0-0', style: { strokeColor: '#000000' } },
    ]
    syncMindMapConnectionStrokeColorsForCanvasMode(connections, nodes, 'v2')
    expect(connections[0].style?.strokeColor).toBe('#2563eb')
  })

  it('sanitizeLegacyNodeStyle removes v2 nodeShape', () => {
    const cleaned = sanitizeLegacyNodeStyle({
      nodeShape: 'underline',
      backgroundColor: '#fff',
      borderColor: '#000',
    })
    expect(cleaned.nodeShape).toBeUndefined()
    expect(cleaned.backgroundColor).toBeUndefined()
    expect(cleaned.borderColor).toBeUndefined()
  })

  it('snapshotMindMapCanvasBucket stores path-keyed styles per mode', () => {
    const data: DiagramData = {
      type: 'mindmap',
      nodes: [
        { id: 'topic', text: 'T', type: 'topic' },
        {
          id: 'branch-r-0-0',
          text: 'A',
          type: 'branch',
          data: { branchIndex: 0 },
          style: { nodeShape: 'rounded', backgroundColor: '#eee' },
        },
      ],
      connections: [{ id: 'e0', source: 'topic', target: 'branch-r-0-0' }],
      _node_styles: { 'branch-r-0-0': { nodeShape: 'rounded' } },
    }
    snapshotMindMapCanvasBucket(data, 'v2')
    snapshotMindMapCanvasBucket(data, 'legacy')
    expect(data._mindmap_canvas?.v2?.node_styles_by_path?.['r/0']?.nodeShape).toBe('rounded')
    expect(data._mindmap_canvas?.legacy?.node_styles_by_path?.['r/0']?.nodeShape).toBeUndefined()
  })

  it('hydrateMindMapCanvasStylesOnLoad applies legacy bucket and strips v2 fields', () => {
    const data: DiagramData = {
      type: 'mindmap',
      nodes: [
        { id: 'topic', text: 'T', type: 'topic' },
        {
          id: 'branch-r-0-0',
          text: 'A',
          type: 'branch',
          data: { branchIndex: 0 },
          style: { nodeShape: 'rounded', backgroundColor: '#111' },
        },
      ],
      connections: [{ id: 'e0', source: 'topic', target: 'branch-r-0-0' }],
      _node_styles: { 'branch-r-0-0': { nodeShape: 'rounded' } },
      _mindmap_canvas: {
        legacy: {
          node_styles_by_path: {
            'r/0': { backgroundColor: '#eee', borderColor: '#000' },
          },
        },
      },
    }
    hydrateMindMapCanvasStylesOnLoad(data, 'legacy')
    expect(data.nodes[1].style?.nodeShape).toBeUndefined()
    expect(data.nodes[1].style?.backgroundColor).toBeUndefined()
    expect(data._mindmap_theme).toBeUndefined()
  })

  it('reconcileMindMapCanvasModeSwitch restores legacy bucket and clears v2 theme', () => {
    enableMindMapV2CanvasFlag()
    const uiStore = useUIStore()
    uiStore.mindMapCanvasMode = 'legacy'

    const loaded = loadMindMapSpec({
      topic: 'Topic',
      rightBranches: [{ text: 'Branch A' }],
      leftBranches: [],
      preserveLeftRight: true,
    })
    const data: DiagramData = {
      type: 'mindmap',
      nodes: loaded.nodes,
      connections: loaded.connections,
      _mindmap_theme: 'ocean',
      _node_styles: {},
      _mindmap_canvas: {
        legacy: {
          node_styles_by_path: {
            'r/0': { backgroundColor: '#fafafa', borderColor: '#333' },
          },
        },
        v2: {
          node_styles_by_path: {
            'r/0': { nodeShape: 'rounded', backgroundColor: '#fff' },
          },
          theme: 'ocean',
        },
      },
    }
    const ctx = makeMindMapCtx(data)
    const changed = reconcileMindMapCanvasModeSwitch(ctx, 'v2', 'legacy')
    expect(changed).toBe(true)
    expect(data._mindmap_theme).toBeUndefined()
    const branchNode = data.nodes.find((n) => n.id.startsWith('branch-r-1'))
    expect(branchNode?.style?.nodeShape).toBeUndefined()
    expect(branchNode?.style?.backgroundColor).toBeUndefined()
    const branchConn = data.connections?.find((c) => c.source === 'topic')
    expect(branchConn?.style?.strokeColor).toBe(getMindmapBranchColor(0, 'legacy').border)
  })

  it('legacy loadMindMapSpec uses indexed topic handles and column layout', () => {
    const uiStore = useUIStore()
    uiStore.mindMapCanvasMode = 'legacy'

    const result = loadMindMapSpec({
      topic: 'Topic',
      rightBranches: [
        {
          text: 'A',
          children: [{ text: 'A1' }, { text: 'A2' }],
        },
        { text: 'B' },
      ],
      leftBranches: [],
      preserveLeftRight: true,
    })

    const topicEdge = result.connections.find((c) => c.source === 'topic')
    expect(topicEdge?.sourceHandle).toMatch(/^mindmap-right-\d+$/)

    const child1 = result.nodes.find((n) => n.text === 'A1')
    const child2 = result.nodes.find((n) => n.text === 'A2')
    expect(child1?.position?.x).toBe(child2?.position?.x)
    expect(topicEdge?.style?.strokeColor).toBe(getMindmapBranchColor(0, 'legacy').border)
  })

  it('legacy palette uses material colors distinct from shared radix branch hues', () => {
    expect(getMindmapBranchColor(0, 'legacy').fill).toBe('#e3f2fd')
    expect(getMindmapBranchColor(0, 'legacy').border).toBe('#0d47a1')
    expect(getMindmapBranchColor(0).fill).toBe('#e6f4fe')
    expect(LEGACY_MINDMAP_BRANCH_COLORS.length).toBe(20)
  })

  it('legacy loadMindMapSpec does not emit v2 trunk handles', () => {
    const uiStore = useUIStore()
    uiStore.mindMapCanvasMode = 'legacy'

    const result = loadMindMapSpec({
      topic: 'Topic',
      rightBranches: [{ text: 'Only' }],
      leftBranches: [],
      preserveLeftRight: true,
    })

    const trunkHandles = result.connections
      .filter((c) => c.source === 'topic')
      .map((c) => c.sourceHandle)
    expect(trunkHandles).not.toContain('mindmap-right')
    expect(trunkHandles).not.toContain('mindmap-left')
  })

  it('legacy loadMindMapSpec assigns sequential right handles when side is uneven', () => {
    const uiStore = useUIStore()
    uiStore.mindMapCanvasMode = 'legacy'

    const result = loadMindMapSpec({
      topic: 'Topic',
      rightBranches: [{ text: 'R1' }, { text: 'R2' }, { text: 'R3' }, { text: 'R4' }],
      leftBranches: [{ text: 'L1' }],
      preserveLeftRight: true,
    })

    const rightHandles = result.connections
      .filter((c) => c.source === 'topic' && c.target.startsWith('branch-r-'))
      .map((c) => c.sourceHandle)
    expect(rightHandles).toEqual([
      'mindmap-right-0',
      'mindmap-right-1',
      'mindmap-right-2',
      'mindmap-right-3',
    ])
    const leftHandles = result.connections
      .filter((c) => c.source === 'topic' && c.target.startsWith('branch-l-'))
      .map((c) => c.sourceHandle)
    expect(leftHandles).toEqual(['mindmap-left-0'])
  })

  it('legacy addMindMapBranch redistributes clockwise instead of forcing right', () => {
    const uiStore = useUIStore()
    uiStore.mindMapCanvasMode = 'legacy'

    const loaded = loadMindMapSpec({
      topic: 'Topic',
      rightBranches: [{ text: 'OnlyRight' }],
      leftBranches: [],
      preserveLeftRight: true,
    })
    const ctx = makeMindMapCtx({
      type: 'mindmap',
      nodes: loaded.nodes,
      connections: loaded.connections,
    })
    const ops = useMindMapOpsSlice(ctx)

    expect(ops.addMindMapBranch('right', 'NewBranch', 'Child')).toBe(true)

    const leftTopicEdge = ctx.data.value?.connections?.find(
      (c) => c.source === 'topic' && c.target.startsWith('branch-l-')
    )
    expect(leftTopicEdge?.target).toBeDefined()
    const newBranchNode = ctx.data.value?.nodes?.find((n) => n.text === 'NewBranch')
    expect(newBranchNode?.id.startsWith('branch-l-')).toBe(true)
  })

  it('legacy addMindMapBranch seeds two default children', () => {
    const uiStore = useUIStore()
    uiStore.mindMapCanvasMode = 'legacy'

    const loaded = loadMindMapSpec({
      topic: 'Topic',
      rightBranches: [],
      leftBranches: [],
      preserveLeftRight: true,
    })
    const ctx = makeMindMapCtx({
      type: 'mindmap',
      nodes: loaded.nodes,
      connections: loaded.connections,
    })
    const ops = useMindMapOpsSlice(ctx)

    expect(ops.addMindMapBranch('right', 'NewBranch', 'Child')).toBe(true)

    const childTexts =
      ctx.data.value?.nodes
        ?.filter((n) => n.type === 'branch' && n.text !== 'NewBranch')
        .map((n) => n.text) ?? []
    expect(childTexts).toEqual(['Child 1', 'Child 2'])
  })

  it('legacy addMindMapSibling seeds two default children for top-level branches', () => {
    const uiStore = useUIStore()
    uiStore.mindMapCanvasMode = 'legacy'

    const loaded = loadMindMapSpec({
      topic: 'Topic',
      rightBranches: [{ text: 'Branch A', children: [{ text: 'A1' }, { text: 'A2' }] }],
      leftBranches: [],
      preserveLeftRight: true,
    })
    const ctx = makeMindMapCtx({
      type: 'mindmap',
      nodes: loaded.nodes,
      connections: loaded.connections,
    })
    const ops = useMindMapOpsSlice(ctx)

    const anchorId = ctx.data.value?.nodes?.find((n) => n.text === 'Branch A')?.id
    expect(anchorId).toBeDefined()

    expect(ops.addMindMapSibling(anchorId!, 'Branch B')).toBe(true)

    const newBranchNode = ctx.data.value?.nodes?.find((n) => n.text === 'Branch B')
    expect(newBranchNode).toBeDefined()
    const childEdges =
      ctx.data.value?.connections?.filter((c) => c.source === newBranchNode?.id) ?? []
    expect(childEdges).toHaveLength(2)
  })

  it('v2 addMindMapBranch honors explicit side without default children', () => {
    enableMindMapV2CanvasFlag()
    const uiStore = useUIStore()
    uiStore.mindMapCanvasMode = 'v2'

    const loaded = loadMindMapSpec({
      topic: 'Topic',
      rightBranches: [{ text: 'RightOnly' }],
      leftBranches: [],
      preserveLeftRight: true,
    })
    const ctx = makeMindMapCtx({
      type: 'mindmap',
      nodes: loaded.nodes,
      connections: loaded.connections,
    })
    const ops = useMindMapOpsSlice(ctx)

    expect(ops.addMindMapBranch('left', 'LeftBranch', 'Child')).toBe(true)

    const newBranchNode = ctx.data.value?.nodes?.find((n) => n.text === 'LeftBranch')
    expect(newBranchNode?.id.startsWith('branch-l-')).toBe(true)
    const childCount =
      ctx.data.value?.connections?.filter((c) => c.source === newBranchNode?.id).length ?? 0
    expect(childCount).toBe(0)
  })

  it('classic topic handles evenly space per side when branch layout is unavailable', () => {
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'branch-r-1-0', sourceHandle: 'mindmap-right-0' },
      { id: 'e2', source: 'topic', target: 'branch-r-1-1', sourceHandle: 'mindmap-right-1' },
      { id: 'e3', source: 'topic', target: 'branch-l-1-0', sourceHandle: 'mindmap-left-0' },
    ]

    const rightHandles = buildClassicMindMapTopicHandlePositions(
      connections,
      'r',
      'mindmap-right'
    )
    expect(rightHandles.map((h) => h.top)).toEqual(['33.33333333333333%', '66.66666666666666%'])

    const leftHandles = buildClassicMindMapTopicHandlePositions(connections, 'l', 'mindmap-left')
    expect(leftHandles).toEqual([
      { id: 'mindmap-left-0', top: '50%', transform: 'translateY(-50%)' },
    ])
  })

  it('classic topic handles place middle exit at 50% for odd side counts', () => {
    const connections: Connection[] = [
      { id: 'e0', source: 'topic', target: 'branch-r-1-0', sourceHandle: 'mindmap-right-0' },
      { id: 'e1', source: 'topic', target: 'branch-r-1-1', sourceHandle: 'mindmap-right-1' },
      { id: 'e2', source: 'topic', target: 'branch-r-1-2', sourceHandle: 'mindmap-right-2' },
    ]

    const handles = buildClassicMindMapTopicHandlePositions(connections, 'r', 'mindmap-right')
    expect(handles.map((h) => h.top)).toEqual(['25%', '50%', '75%'])
  })

  it('default template assigns two evenly spaced topic handles per side', () => {
    const uiStore = useUIStore()
    uiStore.mindMapCanvasMode = 'legacy'

    const loaded = loadMindMapSpec({
      topic: '中心主题',
      children: Array.from({ length: 4 }, (_, bi) => ({
        text: `分支${bi + 1}`,
        children: [{ text: `子项${bi + 1}.1` }, { text: `子项${bi + 1}.2` }],
      })),
    })

    const rightHandles = buildClassicMindMapTopicHandlePositions(
      loaded.connections,
      'r',
      'mindmap-right'
    )
    const leftHandles = buildClassicMindMapTopicHandlePositions(
      loaded.connections,
      'l',
      'mindmap-left'
    )

    expect(rightHandles.map((h) => h.top)).toEqual(['33.33333333333333%', '66.66666666666666%'])
    expect(leftHandles.map((h) => h.top)).toEqual(['33.33333333333333%', '66.66666666666666%'])
  })

  it('classic topic handles stay evenly spaced with five branches per side', () => {
    const connections: Connection[] = Array.from({ length: 5 }, (_, i) => ({
      id: `e-r-${i}`,
      source: 'topic',
      target: `branch-r-1-${i}`,
      sourceHandle: 'mindmap-right-0',
    }))

    const handles = buildClassicMindMapTopicHandlePositions(connections, 'r', 'mindmap-right')
    expect(handles.map((h) => h.id)).toEqual([
      'mindmap-right-0',
      'mindmap-right-1',
      'mindmap-right-2',
      'mindmap-right-3',
      'mindmap-right-4',
    ])
    expect(handles.map((h) => h.top)).toEqual(
      Array.from({ length: 5 }, (_, i) => `${classicMindMapSideHandleTopPercent(i, 5)}%`)
    )
  })

  it('classic topic edges remap stale sourceHandle ids to sequential evenly spaced handles', () => {
    const connections: Connection[] = [
      { id: 'e0', source: 'topic', target: 'branch-r-1-0', sourceHandle: 'mindmap-right-0' },
      { id: 'e1', source: 'topic', target: 'branch-r-1-1', sourceHandle: 'mindmap-right-0' },
      { id: 'e2', source: 'topic', target: 'branch-r-1-2', sourceHandle: 'mindmap-right-0' },
    ]

    expect(withClassicMindMapTopicSourceHandle(connections[0], connections).sourceHandle).toBe(
      'mindmap-right-0'
    )
    expect(withClassicMindMapTopicSourceHandle(connections[1], connections).sourceHandle).toBe(
      'mindmap-right-1'
    )
    expect(withClassicMindMapTopicSourceHandle(connections[2], connections).sourceHandle).toBe(
      'mindmap-right-2'
    )
  })

  it('classic pill topic handles inset toward semicircle boundary away from center', () => {
    expect(classicMindMapPillHandleInsetPx(48, 50)).toBeCloseTo(0, 5)
    expect(classicMindMapPillHandleInsetPx(48, 16.666666666666668)).toBeGreaterThan(4)

    const connections: Connection[] = [
      { id: 'e0', source: 'topic', target: 'branch-r-1-0', sourceHandle: 'mindmap-right-0' },
      { id: 'e1', source: 'topic', target: 'branch-r-1-1', sourceHandle: 'mindmap-right-1' },
      { id: 'e2', source: 'topic', target: 'branch-r-1-2', sourceHandle: 'mindmap-right-2' },
    ]
    const handles = buildClassicMindMapTopicHandlePositions(
      connections,
      'r',
      'mindmap-right',
      [],
      48
    )
    expect(handles[1]?.transform).toBe('translateY(-50%)')
    expect(handles[0]?.transform).toMatch(/^translate\(-\d+(\.\d+)?px, -50%\)$/)
    expect(handles[2]?.transform).toMatch(/^translate\(-\d+(\.\d+)?px, -50%\)$/)
  })
})
