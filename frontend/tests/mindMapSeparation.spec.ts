import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import {
  resolveLegacyMindMapConnectionStrokeColor,
  syncLegacyMindMapConnectionStrokeColors,
  syncMindMapConnectionStrokeColorsForCanvasMode,
} from '@/config/mindMapGeometry'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import {
  hydrateMindMapCanvasStylesOnLoad,
  reconcileMindMapCanvasModeSwitch,
  sanitizeLegacyNodeStyle,
  snapshotMindMapCanvasBucket,
} from '@/stores/diagram/mindMapCanvasModeSwitch'
import { getEdgeTypeForDiagram } from '@/stores/diagram/events'
import type { DiagramContext } from '@/stores/diagram/types'
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
    feature_askonce: true,
    feature_school_zone: false,
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
    pushHistory: vi.fn(),
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
      getMindmapBranchColor(2).border
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
    ).toBe(getMindmapBranchColor(4).border)
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
    expect(connections[0].style?.strokeColor).toBe(getMindmapBranchColor(0).border)
    expect(connections[1].style?.strokeColor).toBe(getMindmapBranchColor(1).border)
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
    expect(cleaned.backgroundColor).toBe('#fff')
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
    expect(data.nodes[1].style?.backgroundColor).toBe('#eee')
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
    expect(branchNode?.style?.backgroundColor).toBe('#fafafa')
    const branchConn = data.connections?.find((c) => c.source === 'topic')
    expect(branchConn?.style?.strokeColor).toBe(getMindmapBranchColor(0).border)
  })
})
