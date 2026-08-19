/**
 * Production-shaped mind map: Doubao returned a nested child as a bare string
 * (``光场重建与相位编码``) and hydrate crashed assigning ``uid``.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { loadMindMapSpec, nodesAndConnectionsToMindMapSpec } from '@/stores/specLoader/mindMap'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import {
  extractBranchesFromGeneratedSpec,
  normalizeGeneratedBranch,
} from '@/utils/mindMapSubgraphMerge'
import { readMindMapNodeUid, rebindMindMapBranchUidsForPaste } from '@/utils/mindMapNodeUid'

/** Six-branch holography map matching the logged autocomplete topic. */
const HOLOGRAPHY_DOUBAO_SPEC = {
  topic: '全息投影是什么',
  children: [
    {
      text: '光学原理',
      children: [
        '光场重建与相位编码',
        { text: '干涉记录', children: ['参考光', { text: '物光' }] },
        { text: '衍射再现' },
      ],
    },
    {
      text: '记录与再现',
      children: [{ text: '离轴全息' }, { text: '同轴全息' }, '数字全息'],
    },
    {
      text: '系统组成',
      children: [{ text: '激光光源' }, { text: '空间光调制器' }, { text: '投影光学' }],
    },
    {
      text: '应用场景',
      children: [{ text: '教学演示' }, { text: '展览展示' }, { text: '医疗影像' }],
    },
    {
      text: '技术挑战',
      children: [{ text: '计算量' }, '散斑噪声', { text: '视场与景深' }],
    },
    {
      text: '与相关技术对比',
      children: [{ text: '立体显示' }, { text: '增强现实' }],
    },
  ],
}

const EXPECTED_LABELS = [
  '光学原理',
  '光场重建与相位编码',
  '干涉记录',
  '参考光',
  '物光',
  '衍射再现',
  '记录与再现',
  '离轴全息',
  '同轴全息',
  '数字全息',
  '系统组成',
  '激光光源',
  '空间光调制器',
  '投影光学',
  '应用场景',
  '教学演示',
  '展览展示',
  '医疗影像',
  '技术挑战',
  '计算量',
  '散斑噪声',
  '视场与景深',
  '与相关技术对比',
  '立体显示',
  '增强现实',
]

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

describe('mind-map string-child audit (holography)', () => {
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

  it('loads the Doubao-shaped holography spec without throwing', () => {
    const loaded = loadMindMapSpec(HOLOGRAPHY_DOUBAO_SPEC)
    const branchTexts = loaded.nodes.filter((node) => node.type === 'branch').map((node) => node.text)
    expect(branchTexts).toEqual(expect.arrayContaining(EXPECTED_LABELS))
    expect(branchTexts).toHaveLength(EXPECTED_LABELS.length)

    const crashLabel = loaded.nodes.find((node) => node.text === '光场重建与相位编码')
    const uid = readMindMapNodeUid(crashLabel)
    expect(uid).toBeTruthy()
    expect(crashLabel?.id).toBe(uid)

    for (const node of loaded.nodes.filter((item) => item.type === 'branch')) {
      expect(readMindMapNodeUid(node)).toBe(node.id)
    }
  })

  it('round-trips extract → reload with the holography label intact', () => {
    const first = loadMindMapSpec(HOLOGRAPHY_DOUBAO_SPEC)
    const extracted = nodesAndConnectionsToMindMapSpec(first.nodes, first.connections)
    const reloaded = loadMindMapSpec({
      topic: extracted.topic,
      leftBranches: extracted.leftBranches,
      rightBranches: extracted.rightBranches,
      preserveLeftRight: true,
    })
    const holography = reloaded.nodes.find((node) => node.text === '光场重建与相位编码')
    expect(holography).toBeTruthy()
    expect(readMindMapNodeUid(holography)).toBe(holography?.id)
    expect(reloaded.nodes.filter((node) => node.type === 'branch')).toHaveLength(EXPECTED_LABELS.length)
  })

  it('keeps string children on subgraph extract and paste rebind', () => {
    const extracted = extractBranchesFromGeneratedSpec(HOLOGRAPHY_DOUBAO_SPEC)
    expect(extracted).toHaveLength(6)
    const optics = extracted.find((branch) => branch.text === '光学原理')
    expect(optics?.children?.map((child) => child.text)).toEqual(
      expect.arrayContaining(['光场重建与相位编码', '干涉记录', '衍射再现'])
    )

    const mixed = [
      { text: '光学原理', children: ['光场重建与相位编码'] },
    ]
    rebindMindMapBranchUidsForPaste(mixed, new Set())
    expect(mixed[0].children?.[0].text).toBe('光场重建与相位编码')
    expect(mixed[0].children?.[0].uid).toBeTruthy()

    const fromString = normalizeGeneratedBranch('光场重建与相位编码')
    expect(fromString).toEqual({ text: '光场重建与相位编码' })
  })

  it('wraps Doubao-like edges: L1 string, number child, all-string nest', () => {
    const loaded = loadMindMapSpec({
      topic: '全息投影是什么',
      leftBranches: [{ text: '应用场景', children: ['教学演示'] }],
      rightBranches: [{ text: '光学原理', children: [7, '光场重建与相位编码', ''] }],
      preserveLeftRight: true,
    })
    const texts = loaded.nodes.filter((node) => node.type === 'branch').map((node) => node.text)
    expect(texts).toEqual(
      expect.arrayContaining(['应用场景', '教学演示', '光学原理', '7', '光场重建与相位编码'])
    )
    expect(texts).not.toContain('')
    for (const node of loaded.nodes.filter((item) => item.type === 'branch')) {
      expect(readMindMapNodeUid(node)).toBe(node.id)
    }
  })
})
