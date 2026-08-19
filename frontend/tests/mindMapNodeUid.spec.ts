import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { nodesAndConnectionsToMindMapSpec, loadMindMapSpec } from '@/stores/specLoader/mindMap'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import { MINDMAP_LEGACY_ID_DATA_KEY } from '@/utils/mindMapIdentityMigrate'
import {
  MINDMAP_NODE_UID_DATA_KEY,
  readMindMapNodeUid,
  rebindMindMapBranchUidsForPaste,
} from '@/utils/mindMapNodeUid'

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

describe('mindMapUid round-trip', () => {
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

  it('assigns and preserves uids across extract → reload for duplicate labels', () => {
    const first = loadMindMapSpec({
      topic: '中心主题',
      rightBranches: [
        { text: '你好', children: [{ text: '子项1' }] },
        { text: '你好', children: [{ text: '子项2' }] },
      ],
      leftBranches: [],
      preserveLeftRight: true,
    })

    const helloNodes = first.nodes.filter((n) => n.text === '你好')
    expect(helloNodes).toHaveLength(2)
    const uidA = readMindMapNodeUid(helloNodes[0])
    const uidB = readMindMapNodeUid(helloNodes[1])
    expect(uidA).toBeTruthy()
    expect(uidB).toBeTruthy()
    expect(uidA).not.toBe(uidB)
    expect(helloNodes[0]?.id).toBe(uidA)
    expect(helloNodes[1]?.id).toBe(uidB)

    const extracted = nodesAndConnectionsToMindMapSpec(first.nodes, first.connections)
    expect(extracted.rightBranches[0].uid).toBe(uidA)
    expect(extracted.rightBranches[1].uid).toBe(uidB)

    // Swap order (simulates move) while keeping uids on branch specs.
    const reloaded = loadMindMapSpec({
      topic: extracted.topic,
      rightBranches: [extracted.rightBranches[1], extracted.rightBranches[0]],
      leftBranches: [],
      preserveLeftRight: true,
    })

    const byUid = new Map(
      reloaded.nodes
        .filter((n) => n.type === 'branch')
        .map((n) => [readMindMapNodeUid(n), n])
    )
    expect(byUid.get(uidA!)?.text).toBe('你好')
    expect(byUid.get(uidB!)?.text).toBe('你好')
    expect(byUid.get(uidA!)?.data?.[MINDMAP_NODE_UID_DATA_KEY]).toBe(uidA)
    // First L1 is former second branch (uidB) — canvas id is the uid.
    const firstL1 = reloaded.connections.find((c) => c.source === 'topic')?.target
    expect(firstL1).toBe(uidB)
    expect(readMindMapNodeUid(reloaded.nodes.find((n) => n.id === firstL1))).toBe(uidB)
  })

  it('keeps children-only stored UUID ids and leftover invented ids as aliases', () => {
    const loaded = loadMindMapSpec({
      topic: 'Cars',
      children: [
        {
          id: 'uid-diy',
          text: 'DIY',
          children: [{ id: 'branch-r-2-0', text: 'Paint' }],
        },
      ],
    })
    const diy = loaded.nodes.find((node) => node.text === 'DIY')
    const paint = loaded.nodes.find((node) => node.text === 'Paint')
    expect(diy?.id).toBe('uid-diy')
    expect(paint?.id).not.toBe('branch-r-2-0')
    expect(paint?.data?.[MINDMAP_LEGACY_ID_DATA_KEY]).toBe('branch-r-2-0')
    expect(readMindMapNodeUid(paint)).toBe(paint?.id)
  })

  it('wraps bare string children so load can assign canvas uids', () => {
    const loaded = loadMindMapSpec({
      topic: '全息投影是什么',
      children: [
        {
          text: '光学原理',
          children: ['光场重建与相位编码', { text: '干涉记录' }, '  ', ''],
        },
      ],
    })
    const holography = loaded.nodes.find((node) => node.text === '光场重建与相位编码')
    const interference = loaded.nodes.find((node) => node.text === '干涉记录')
    expect(holography).toBeTruthy()
    expect(interference).toBeTruthy()
    const uid = readMindMapNodeUid(holography)
    expect(uid).toBeTruthy()
    expect(holography?.id).toBe(uid)
    expect(loaded.nodes.filter((node) => node.type === 'branch')).toHaveLength(3)
  })

  it('rebinds paste uids when source still exists (copy) but keeps cut uids', () => {
    const copyBranches = [{ text: '你好', uid: 'live-uid', children: [{ text: '子', uid: 'live-child' }] }]
    rebindMindMapBranchUidsForPaste(copyBranches, new Set(['live-uid', 'live-child']))
    expect(copyBranches[0].uid).not.toBe('live-uid')
    expect(copyBranches[0].children?.[0].uid).not.toBe('live-child')

    const cutBranches = [{ text: '你好', uid: 'cut-uid' }]
    rebindMindMapBranchUidsForPaste(cutBranches, new Set())
    expect(cutBranches[0].uid).toBe('cut-uid')
  })
})
