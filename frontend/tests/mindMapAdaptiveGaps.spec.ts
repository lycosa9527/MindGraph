import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  DEFAULT_MINDMAP_BRANCH_GAP,
  MINDMAP_MIXED_BRANCH_GAP,
  MINDMAP_MIXED_SIBLING_GAP,
  MINDMAP_SIBLING_GAP,
  MINDMAP_UNDERLINE_BRANCH_GAP,
  MINDMAP_UNDERLINE_SIBLING_GAP,
} from '@/composables/diagrams/layoutConfig'
import {
  mindMapAdaptiveBranchGap,
  mindMapAdaptiveSiblingGap,
  normalizeMindMapPackGaps,
  sumMindMapPairGaps,
} from '@/config/mindMapAdaptiveGaps'
import { loadMindMapSpec } from '@/stores/specLoader/mindMap'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import { computeSymmetricRootStartYs } from '@/utils/mindMapSideStacking'

function enableMindMapV2Canvas(): void {
  const flagsStore = useFeatureFlagsStore()
  flagsStore.flags = {
    external_base_url: '',
    feature_rag_chunk_test: false,
    feature_course: false,
    feature_mate_learning: false,
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
    feature_mindmate_collab: false,
    feature_markets: false,
    feature_mindbot: false,
    feature_mindmate_export: false,
    feature_kitty_agent: false,
    feature_auth_pixel_battle: false,
    feature_test_server_banner: false,
    feature_oauth_login: false,
    feature_thinking_coins: false,
    workshop_chat_preview_org_ids: [],
    feature_org_access: {},
  }
  useUIStore().mindMapCanvasMode = 'v2'
}

function sideSpan(nodes: { id: string; position?: { y: number }; data?: { estimatedHeight?: number } }[]): number {
  const right = nodes.filter((n) => n.id.startsWith('branch-r-') && n.position)
  if (right.length === 0) return 0
  let minY = Infinity
  let maxY = -Infinity
  for (const n of right) {
    if (!n.position) continue
    const h = (n.data?.estimatedHeight as number | undefined) ?? 34
    minY = Math.min(minY, n.position.y)
    maxY = Math.max(maxY, n.position.y + h)
  }
  return maxY - minY
}

describe('mindMapAdaptiveGaps', () => {
  it('gap matrix: underline tight, box default, mixed in between', () => {
    expect(mindMapAdaptiveSiblingGap('underline', 'underline')).toBe(MINDMAP_UNDERLINE_SIBLING_GAP)
    expect(mindMapAdaptiveSiblingGap('rectangle', 'rectangle')).toBe(MINDMAP_SIBLING_GAP)
    expect(mindMapAdaptiveSiblingGap('oval', 'rounded')).toBe(MINDMAP_SIBLING_GAP)
    expect(mindMapAdaptiveSiblingGap('underline', 'oval')).toBe(MINDMAP_MIXED_SIBLING_GAP)
    expect(mindMapAdaptiveSiblingGap('rectangle', 'underline')).toBe(MINDMAP_MIXED_SIBLING_GAP)

    expect(mindMapAdaptiveBranchGap('underline', 'underline')).toBe(MINDMAP_UNDERLINE_BRANCH_GAP)
    expect(mindMapAdaptiveBranchGap('rectangle', 'rectangle')).toBe(DEFAULT_MINDMAP_BRANCH_GAP)
    expect(mindMapAdaptiveBranchGap('underline', 'rectangle')).toBe(MINDMAP_MIXED_BRANCH_GAP)
  })

  it('normalizeMindMapPackGaps keeps scalar API for symmetric pack tests', () => {
    expect(normalizeMindMapPackGaps(3, 28)).toEqual([28, 28])
    expect(normalizeMindMapPackGaps(3, [14, 20])).toEqual([14, 20])
    const starts = computeSymmetricRootStartYs([40, 40, 40], 100, 28)
    expect(starts).toHaveLength(3)
    expect(starts[1]! - starts[0]!).toBe(40 + 28)
  })

  it('sumMindMapPairGaps sums consecutive pairs', () => {
    expect(
      sumMindMapPairGaps(
        ['underline', 'underline', 'oval', 'underline'],
        mindMapAdaptiveSiblingGap
      )
    ).toBe(
      MINDMAP_UNDERLINE_SIBLING_GAP + MINDMAP_MIXED_SIBLING_GAP + MINDMAP_MIXED_SIBLING_GAP
    )
  })
})

describe('adaptive layout across 导图样式', () => {
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

  const tree = {
    topic: '主题',
    children: [
      {
        text: '一级A',
        children: [{ text: '二级1' }, { text: '二级2' }, { text: '二级3' }],
      },
      {
        text: '一级B',
        children: [{ text: '二级4' }, { text: '二级5' }],
      },
    ],
  }

  it('underline style packs more compact than formal on the same tree', () => {
    const underline = loadMindMapSpec({ ...tree, _mindmap_diagram_style: 'underline' })
    const formal = loadMindMapSpec({ ...tree, _mindmap_diagram_style: 'formal' })
    expect(sideSpan(underline.nodes)).toBeLessThan(sideSpan(formal.nodes))
  })

  it('mostly-underline column with one oval uses mixed gaps only at the oval', () => {
    const loaded = loadMindMapSpec({
      topic: 'T',
      _mindmap_diagram_style: 'underline',
      children: [
        {
          text: 'L1',
          children: [
            { text: 'u1' },
            { text: 'u2' },
            { text: 'oval-node' },
            { text: 'u3' },
          ],
        },
      ],
    })
    const kids = loaded.nodes
      .filter((n) => n.id.startsWith('branch-r-2-'))
      .sort((a, b) => (a.position?.y ?? 0) - (b.position?.y ?? 0))
    expect(kids).toHaveLength(4)

    // Stamp one middle child as oval (manual override scenario).
    const withOval = kids.map((n, i) =>
      i === 2
        ? { ...n, style: { ...n.style, nodeShape: 'oval' as const } }
        : { ...n, style: { ...n.style, nodeShape: 'underline' as const } }
    )
    const h = (n: (typeof withOval)[0]) => (n.data?.estimatedHeight as number) ?? 22
    const gap01 = (withOval[1]!.position!.y) - (withOval[0]!.position!.y + h(withOval[0]!))
    const gap12 = (withOval[2]!.position!.y) - (withOval[1]!.position!.y + h(withOval[1]!))
    const gap23 = (withOval[3]!.position!.y) - (withOval[2]!.position!.y + h(withOval[2]!))

    // Initial load is all-underline: gaps between L2 should be underline sibling gap.
    expect(gap01).toBeCloseTo(MINDMAP_UNDERLINE_SIBLING_GAP, 0)
    expect(gap12).toBeCloseTo(MINDMAP_UNDERLINE_SIBLING_GAP, 0)
    expect(gap23).toBeCloseTo(MINDMAP_UNDERLINE_SIBLING_GAP, 0)

    // Pairwise helper for the mixed override case (restack would use these).
    expect(mindMapAdaptiveSiblingGap('underline', 'underline')).toBe(MINDMAP_UNDERLINE_SIBLING_GAP)
    expect(mindMapAdaptiveSiblingGap('underline', 'oval')).toBe(MINDMAP_MIXED_SIBLING_GAP)
    expect(mindMapAdaptiveSiblingGap('oval', 'underline')).toBe(MINDMAP_MIXED_SIBLING_GAP)
  })
})
