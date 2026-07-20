/**
 * Shared verified commit used by WS diagram_update and Kitty branch autocomplete.
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  commitVerifiedLocalDiagramMutation,
  verifySubgraphChildTextsPresent,
} from '@/composables/kitty/diagramEditApply'
import * as hubPersistModule from '@/composables/kitty/diagramEditHubPersist'
import { useDiagramStore } from '@/stores/diagram'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import { captureDiagramFingerprint } from '@/utils/diagramEditVerify'

function stubMatchMedia(): void {
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
}

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

describe('commitVerifiedLocalDiagramMutation', () => {
  beforeEach(() => {
    stubMatchMedia()
    setActivePinia(createPinia())
    enableMindMapV2CanvasFlag()
    useUIStore().mindMapCanvasMode = 'v2'
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => 'v2'),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })
  })

  it('verifySubgraphChildTextsPresent accepts placeholder-replace (no node-count delta)', () => {
    const evidence = captureDiagramFingerprint(
      [
        { id: 'topic', text: 'Cars', type: 'topic' },
        { id: 'branch-r-1-0', text: 'Paint', type: 'branch' },
      ] as never,
      [{ id: 'e1', source: 'topic', target: 'branch-r-1-0' }] as never
    )
    expect(verifySubgraphChildTextsPresent(evidence, ['Paint']).ok).toBe(true)
    expect(verifySubgraphChildTextsPresent(evidence, ['Missing']).ok).toBe(false)
  })

  it('rolls back Pinia when Hub persist fails', async () => {
    const store = useDiagramStore()
    store.loadFromSpec(
      {
        topic: 'Cars',
        leftBranches: [],
        rightBranches: [{ text: 'DIY', children: [] }],
      },
      'mindmap'
    )
    const beforeCount = store.data?.nodes?.length ?? 0

    vi.spyOn(hubPersistModule, 'persistVerifiedDiagramToHub').mockResolvedValue({
      ok: false,
      error: 'timeout',
    })

    const result = await commitVerifiedLocalDiagramMutation({
      apply: () =>
        store.pasteMindMapClipboardBranches('branch-r-1-0', [{ text: 'Brush' }], 'test'),
      mutationId: 'mut-ac-1',
      verify: (_b, after) => verifySubgraphChildTextsPresent(after, ['Brush']),
      hubPersist: {
        buildContext: () =>
          ({
            diagram_type: 'mindmap',
            active_panel: 'none',
            selected_nodes: [],
            diagram_data: {},
          }) as never,
        updateContext: vi.fn(),
        hubScopeRevision: null,
      },
      requireHubPersist: true,
    })

    expect(result.verified).toBe(false)
    expect(result.hubPersistOk).toBe(false)
    expect(store.data?.nodes?.some((n) => n.text === 'Brush')).toBe(false)
    expect(store.data?.nodes?.length).toBe(beforeCount)
  })

  it('keeps Pinia when Hub persist succeeds', async () => {
    const store = useDiagramStore()
    store.loadFromSpec(
      {
        topic: 'Cars',
        leftBranches: [],
        rightBranches: [{ text: 'DIY', children: [] }],
      },
      'mindmap'
    )

    vi.spyOn(hubPersistModule, 'persistVerifiedDiagramToHub').mockResolvedValue({
      ok: true,
      revision: 9,
    })

    const result = await commitVerifiedLocalDiagramMutation({
      apply: () =>
        store.pasteMindMapClipboardBranches('branch-r-1-0', [{ text: 'Brush' }], 'test'),
      mutationId: 'mut-ac-2',
      verify: (_b, after) => verifySubgraphChildTextsPresent(after, ['Brush']),
      hubPersist: {
        buildContext: () =>
          ({
            diagram_type: 'mindmap',
            active_panel: 'none',
            selected_nodes: [],
            diagram_data: {},
          }) as never,
        updateContext: vi.fn(),
        hubScopeRevision: null,
      },
      requireHubPersist: true,
    })

    expect(result.verified).toBe(true)
    expect(result.hubPersistOk).toBe(true)
    expect(result.hubRevision).toBe(9)
    expect(store.data?.nodes?.some((n) => n.text === 'Brush')).toBe(true)
  })
})
