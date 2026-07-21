import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  mergeMindMapReloadStyles,
  mindMapNodePathKey,
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
