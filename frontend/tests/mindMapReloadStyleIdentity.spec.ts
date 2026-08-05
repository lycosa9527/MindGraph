import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  applyMindMapStylesByPath,
  buildMindMapStyleForNewBranchNode,
  collectMindMapStylesByPath,
  mergeMindMapReloadStyles,
  mindMapNodePathKey,
  resolveMindMapLiveSiblingStyle,
} from '@/stores/diagram/mindMapStylePreservation'
import { remapMindMapNodeIdAfterReload } from '@/stores/diagram/mindMapCollapse'
import { loadMindMapSpec } from '@/stores/specLoader/mindMap'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import type { Connection, DiagramNode, NodeStyle } from '@/types'

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

describe('mindmap reload style identity', () => {
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
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    enableMindMapV2Canvas()
  })

  it('keeps custom colors with moved content and updates shape for new depth', () => {
    const before = loadMindMapSpec({
      topic: '中心主题',
      rightBranches: [
        {
          text: '分支A',
          children: [{ text: '子项A1' }],
        },
        { text: '分支B' },
      ],
      leftBranches: [],
      preserveLeftRight: true,
    })

    const branchA = before.nodes.find((n) => n.text === '分支A')
    expect(branchA).toBeTruthy()
    const custom: NodeStyle = {
      backgroundColor: '#ffe4e6',
      borderColor: '#be123c',
      textColor: '#881337',
      nodeShape: 'rounded',
    }
    branchA!.style = { ...custom }
    const existingStyles: Record<string, NodeStyle> = {
      [branchA!.id]: { ...custom },
    }

    // Reparent 分支A under 分支B (depth 1 → 2).
    const after = loadMindMapSpec({
      topic: '中心主题',
      rightBranches: [
        {
          text: '分支B',
          children: [
            {
              text: '分支A',
              children: [{ text: '子项A1' }],
            },
          ],
        },
      ],
      leftBranches: [],
      preserveLeftRight: true,
    })

    const merged = mergeMindMapReloadStyles(
      before.nodes,
      before.connections,
      after.nodes,
      after.connections,
      existingStyles,
      null,
      'classic',
      remapMindMapNodeIdAfterReload
    )

    const moved = after.nodes.find((n) => n.text === '分支A')
    expect(moved).toBeTruthy()
    expect(merged[moved!.id]?.backgroundColor).toBe('#ffe4e6')
    expect(merged[moved!.id]?.borderColor).toBe('#be123c')
    // Classic L2 uses underline when depth changes.
    expect(merged[moved!.id]?.nodeShape).toBe('underline')
    expect(moved!.style?.nodeShape).toBe('underline')
  })

  it('new same-row path inherits sibling colors and shape (not parent)', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic' },
      {
        id: 'branch-r-1-0',
        text: 'Existing',
        type: 'branch',
        style: {
          backgroundColor: '#dbeafe',
          borderColor: '#0f766e',
          textColor: '#134e4a',
          nodeShape: 'oval',
        },
      },
      { id: 'branch-r-1-1', text: '新分支', type: 'branch' },
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-r-1-1' },
    ]
    const stylesByPath = collectMindMapStylesByPath(nodes.slice(0, 2), connections)
    const merged = applyMindMapStylesByPath(
      nodes,
      connections,
      stylesByPath,
      'vibrantBlue',
      'bubble'
    )

    expect(merged['branch-r-1-1']?.backgroundColor).toBe('#dbeafe')
    expect(merged['branch-r-1-1']?.borderColor).toBe('#0f766e')
    expect(merged['branch-r-1-1']?.textColor).toBe('#134e4a')
    expect(merged['branch-r-1-1']?.nodeShape).toBe('oval')
  })

  it('insert-above (index 0) still inherits from the later sibling', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic' },
      { id: 'branch-r-1-0', text: '新分支', type: 'branch' },
      {
        id: 'branch-r-1-1',
        text: 'Existing',
        type: 'branch',
        style: {
          backgroundColor: '#f3e8ff',
          borderColor: '#6366f1',
          nodeShape: 'rounded',
        },
      },
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-r-1-1' },
    ]
    // Only the existing sibling has a preserved path style.
    const stylesByPath = new Map<string, NodeStyle>([
      [
        'r/1',
        {
          backgroundColor: '#f3e8ff',
          borderColor: '#6366f1',
          nodeShape: 'rounded',
        },
      ],
    ])
    const merged = applyMindMapStylesByPath(
      nodes,
      connections,
      stylesByPath,
      'vibrantBlue',
      'classic'
    )

    expect(merged['branch-r-1-0']?.backgroundColor).toBe('#f3e8ff')
    expect(merged['branch-r-1-0']?.nodeShape).toBe('rounded')
  })

  it('buildMindMapStyleForNewBranchNode matches live sibling style', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic' },
      {
        id: 'branch-r-1-0',
        text: 'A',
        type: 'branch',
        style: {
          backgroundColor: '#e2e8f0',
          borderColor: '#64748b',
          textColor: '#334155',
          nodeShape: 'oval',
        },
      },
      { id: 'branch-r-1-2', text: '新分支', type: 'branch' },
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-r-1-2' },
    ]
    const siblingStyle = resolveMindMapLiveSiblingStyle(
      'branch-r-1-2',
      nodes,
      connections,
      undefined
    )
    expect(siblingStyle?.backgroundColor).toBe('#e2e8f0')

    const seeded = buildMindMapStyleForNewBranchNode(
      { id: 'branch-r-1-2', type: 'branch' },
      connections,
      {
        themeId: 'morandi',
        diagramStyleId: 'soft',
        siblingStyle,
      }
    )
    expect(seeded.backgroundColor).toBe('#e2e8f0')
    expect(seeded.borderColor).toBe('#64748b')
    expect(seeded.nodeShape).toBe('oval')
  })

  it('live sibling style ignores opposite-side L1 under topic', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic' },
      {
        id: 'branch-r-1-0',
        text: 'Right',
        type: 'branch',
        style: {
          backgroundColor: '#ff0000',
          borderColor: '#990000',
          nodeShape: 'oval',
        },
      },
      { id: 'branch-l-1-0', text: 'Left new', type: 'branch' },
    ]
    // Loader order: rights then lefts — left's "earlier" topic child is the right branch.
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-l-1-0' },
    ]
    const siblingStyle = resolveMindMapLiveSiblingStyle(
      'branch-l-1-0',
      nodes,
      connections,
      undefined
    )
    expect(siblingStyle).toBeUndefined()

    const seeded = buildMindMapStyleForNewBranchNode(
      { id: 'branch-l-1-0', type: 'branch' },
      connections,
      {
        themeId: 'vibrantBlue',
        diagramStyleId: 'bubble',
        siblingStyle,
      }
    )
    expect(seeded.backgroundColor).not.toBe('#ff0000')
    expect(seeded.nodeShape).toBe('oval') // bubble L1 preset, not copied from right
  })

  it('rainbow new L1 keeps its own accent (does not copy sibling fill)', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic' },
      {
        id: 'branch-r-1-0',
        text: 'A',
        type: 'branch',
        style: {
          backgroundColor: '#FA8055',
          borderColor: '#d96c48',
          textColor: '#ffffff',
          nodeShape: 'rounded',
        },
      },
      { id: 'branch-r-1-1', text: 'B', type: 'branch' },
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-r-1-1' },
    ]
    const stylesByPath = collectMindMapStylesByPath(nodes.slice(0, 2), connections)
    const merged = applyMindMapStylesByPath(
      nodes,
      connections,
      stylesByPath,
      'rainbow',
      'classic'
    )
    expect(merged['branch-r-1-1']?.backgroundColor).toBeTruthy()
    expect(merged['branch-r-1-1']?.backgroundColor).not.toBe('#FA8055')

    const seeded = buildMindMapStyleForNewBranchNode(
      { id: 'branch-r-1-1', type: 'branch' },
      connections,
      {
        themeId: 'rainbow',
        diagramStyleId: 'classic',
        siblingStyle: nodes[1].style,
      }
    )
    expect(seeded.backgroundColor).not.toBe('#FA8055')
  })

  it('first L2 under styled L1 uses depth preset underline (not parent oval)', () => {
    const before = loadMindMapSpec({
      topic: '中心主题',
      rightBranches: [{ text: '父分支', children: [] }],
      leftBranches: [],
      preserveLeftRight: true,
      diagramStyleId: 'bubble',
    })
    const parent = before.nodes.find((n) => n.text === '父分支')
    expect(parent).toBeTruthy()
    parent!.style = {
      backgroundColor: '#dbeafe',
      borderColor: '#0f766e',
      nodeShape: 'oval',
    }
    const existingStyles: Record<string, NodeStyle> = {
      [parent!.id]: { ...parent!.style! },
    }

    const after = loadMindMapSpec({
      topic: '中心主题',
      rightBranches: [{ text: '父分支', children: [{ text: '子项' }] }],
      leftBranches: [],
      preserveLeftRight: true,
      diagramStyleId: 'bubble',
    })
    const merged = mergeMindMapReloadStyles(
      before.nodes,
      before.connections,
      after.nodes,
      after.connections,
      existingStyles,
      'vibrantBlue',
      'bubble',
      remapMindMapNodeIdAfterReload
    )
    const child = after.nodes.find((n) => n.text === '子项')
    expect(child).toBeTruthy()
    expect(merged[child!.id]?.nodeShape).toBe('underline')
    expect(merged[child!.id]?.backgroundColor).not.toBe('#dbeafe')
  })

  it('reload new sibling keeps sibling shape over loader depth stub', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic' },
      {
        id: 'branch-r-1-0',
        text: 'A',
        type: 'branch',
        style: {
          backgroundColor: '#e2e8f0',
          borderColor: '#64748b',
          nodeShape: 'oval',
        },
      },
      // Loader stub: classic L1 would be rounded
      {
        id: 'branch-r-1-1',
        text: '新分支',
        type: 'branch',
        style: { nodeShape: 'rounded' },
      },
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-r-1-1' },
    ]
    const stylesByPath = collectMindMapStylesByPath(nodes.slice(0, 2), connections)
    const merged = applyMindMapStylesByPath(
      nodes,
      connections,
      stylesByPath,
      'vibrantBlue',
      'classic'
    )
    expect(merged['branch-r-1-1']?.nodeShape).toBe('oval')
    expect(merged['branch-r-1-1']?.backgroundColor).toBe('#e2e8f0')
    expect(nodes.find((n) => n.id === 'branch-r-1-1')?.style?.nodeShape).toBe('oval')
  })

  it('path-keyed merge without remapper keeps styles on slots', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic' },
      {
        id: 'branch-r-1-0',
        text: 'A',
        type: 'branch',
        style: { backgroundColor: '#111111', nodeShape: 'rounded' },
      },
      {
        id: 'branch-r-1-1',
        text: 'B',
        type: 'branch',
        style: { backgroundColor: '#222222', nodeShape: 'rounded' },
      },
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-r-1-1' },
    ]

    // Swap content at same paths (as if style stuck to slots).
    const newNodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic' },
      { id: 'branch-r-1-0', text: 'B', type: 'branch' },
      { id: 'branch-r-1-1', text: 'A', type: 'branch' },
    ]
    const merged = mergeMindMapReloadStyles(
      nodes,
      connections,
      newNodes,
      connections,
      undefined,
      null,
      'classic'
    )

    const path0 = mindMapNodePathKey('branch-r-1-0', connections)
    expect(path0).toBe('r/0')
    expect(merged['branch-r-1-0']?.backgroundColor).toBe('#111111')
    expect(merged['branch-r-1-1']?.backgroundColor).toBe('#222222')
  })
})
