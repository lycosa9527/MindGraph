import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import { MINDMAP_NODE_UID_DATA_KEY } from '@/utils/mindMapNodeUid'

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

function flushRecalcFrames(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve())
    })
  })
}

describe('mindMapPreserveIncomingY policy', () => {
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

  it('sets preserve on L1 Enter, pending inline edit, and write-backs store Y', async () => {
    enableMindMapV2Canvas()
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('mindmap')

    const left = diagramStore.data?.nodes.find((node) => node.id.startsWith('branch-l-1-'))
    expect(left).toBeTruthy()
    if (!left) {
      throw new Error('expected left branch node')
    }
    left.data = {
      ...left.data,
      [MINDMAP_NODE_UID_DATA_KEY]: 'anchor-uid',
      estimatedHeight: 40,
    }

    diagramStore.selectNodes(left.id)
    expect(diagramStore.addMindMapSibling(left.id, '新分支')).toBe(true)
    expect(diagramStore.mindMapPreserveIncomingY).toBe(true)

    const createdBeforeSync = diagramStore.data?.nodes.find((node) => node.text === '新分支')
    expect(createdBeforeSync?.position?.y).toBeTypeOf('number')
    // Post-add edit target is armed until the new host focuses (or retries expire).
    expect(diagramStore.mindMapPendingEditNodeId).toBe(createdBeforeSync?.id)
    expect(diagramStore.selectedNodes[0]).toBe(createdBeforeSync?.id)

    await flushRecalcFrames()

    const created = diagramStore.data?.nodes.find((node) => node.text === '新分支')
    const anchor = diagramStore.data?.nodes.find(
      (node) => node.data?.[MINDMAP_NODE_UID_DATA_KEY] === 'anchor-uid'
    )
    expect(created?.position?.y).toBeTypeOf('number')
    expect(anchor?.position?.y).toBeTypeOf('number')
    // Write-back kept a coherent side pack (new sibling below anchor).
    expect(created?.position?.y).toBeGreaterThan(anchor?.position?.y ?? Number.NaN)
  })

  it('clears preserve on collapse so full Y restack can run', () => {
    enableMindMapV2Canvas()
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('mindmap')

    const parentWithKids = diagramStore.data?.nodes.find(
      (node) =>
        node.id.startsWith('branch-') &&
        (diagramStore.data?.connections ?? []).some((c) => c.source === node.id)
    )
    expect(parentWithKids).toBeTruthy()
    if (!parentWithKids) {
      throw new Error('expected parent with children')
    }

    const l1 = diagramStore.data?.nodes.find((node) => node.id.startsWith('branch-l-1-'))
    expect(l1).toBeTruthy()
    if (!l1) {
      throw new Error('expected L1 branch node')
    }
    diagramStore.selectNodes(l1.id)
    expect(diagramStore.addMindMapSibling(l1.id, '新分支')).toBe(true)
    expect(diagramStore.mindMapPreserveIncomingY).toBe(true)

    expect(diagramStore.toggleMindMapCollapse(parentWithKids.id)).toBe(true)
    expect(diagramStore.mindMapPreserveIncomingY).toBe(false)
    expect(diagramStore.mindMapPreserveIncomingYNodeId).toBeNull()
  })
})
