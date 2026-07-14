/**
 * Verified diagram edit apply: canvas mutations + combined ack contract.
 */
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import { applyVerifiedDiagramUpdate } from '@/composables/kitty/diagramEditApply'
import * as hubPersistModule from '@/composables/kitty/diagramEditHubPersist'
import { useDiagramStore } from '@/stores/diagram'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'

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

function topicOnlyMindmapStore(): ReturnType<typeof useDiagramStore> {
  const store = useDiagramStore()
  store.loadFromSpec(
    {
      topic: 'Cars',
      leftBranches: [],
      rightBranches: [],
    },
    'mindmap'
  )
  return store
}

describe('diagramEditApply one-sentence canvas path', () => {
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

  afterEach(() => {
    eventBus.off('voice:context_mutation_ack')
    vi.restoreAllMocks()
  })

  it('add_nodes DIY branch mutates canvas node count', async () => {
    const store = topicOnlyMindmapStore()
    const beforeCount = store.data?.nodes.length ?? 0
    const sendAck = vi.fn()

    const result = await applyVerifiedDiagramUpdate('add_nodes', [{ text: 'DIY' }], {
      mutationId: 'mut-add-diy',
      sendAck,
      hubRevision: 1,
    })

    const afterCount = store.data?.nodes.length ?? 0
    expect(afterCount).toBeGreaterThan(beforeCount)
    expect(store.data?.nodes.some((n) => String(n.text ?? '').includes('DIY'))).toBe(true)
    expect(result.applied).toBe(true)
    expect(result.verified).toBe(true)
    expect(sendAck).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'diagram_mutation_ack',
        mutation_id: 'mut-add-diy',
        verified: true,
        created_node_ids: expect.arrayContaining([
          expect.stringMatching(/^branch-/),
        ]),
      })
    )
  })

  it('add_nodes with expected effect verifies DIY branch on canvas', async () => {
    const store = topicOnlyMindmapStore()
    const beforeCount = store.data?.nodes.length ?? 0
    const sendAck = vi.fn()

    const persistSpy = vi
      .spyOn(hubPersistModule, 'persistVerifiedDiagramToHub')
      .mockResolvedValue({ ok: true, revision: 5 })

    const result = await applyVerifiedDiagramUpdate('add_nodes', [{ text: 'DIY' }], {
      mutationId: 'mut-add-diy-verify',
      expectedEffect: { op: 'add_branch', text: 'DIY', parent_ref: 'topic' },
      sendAck,
      hubRevision: 4,
      hubPersist: {
        buildContext: () => ({
          diagram_type: 'mindmap',
          active_panel: 'one_sentence',
          selected_nodes: [],
          diagram_data: { children: [] },
          one_sentence_phase: 'edit',
        }),
        updateContext: vi.fn(),
        hubScopeRevision: 4,
        scope: 'scope-1',
        timeoutMs: 300,
      },
    })

    expect(result.verified).toBe(true)
    expect(result.hubPersistOk).toBe(true)
    expect(result.hubRevision).toBe(5)
    expect((store.data?.nodes.length ?? 0) - beforeCount).toBe(1)
    expect(persistSpy).toHaveBeenCalledTimes(1)
    expect(sendAck).toHaveBeenCalledWith(
      expect.objectContaining({
        hub_persist_ok: true,
        hub_revision: 5,
        verified: true,
      })
    )
  })

  it('update_center changes topic text on canvas', async () => {
    const store = topicOnlyMindmapStore()
    const sendAck = vi.fn()

    const result = await applyVerifiedDiagramUpdate('update_center', { new_text: 'Electric Cars' }, {
      mutationId: 'mut-upd-center',
      expectedEffect: { op: 'update_center', text: 'Electric Cars', parent_ref: 'topic' },
      sendAck,
      hubRevision: 3,
    })

    const topic = store.data?.nodes.find((n) => n.id === 'topic')
    expect(topic?.text).toBe('Electric Cars')
    expect(result.verified).toBe(true)
  })

  it('verify failure restores canvas and acks verified false', async () => {
    const store = topicOnlyMindmapStore()
    const beforeCount = store.data?.nodes.length ?? 0
    const sendAck = vi.fn()

    const result = await applyVerifiedDiagramUpdate('add_nodes', [{ text: 'DIY' }], {
      mutationId: 'mut-fail-verify',
      expectedEffect: { op: 'add_branch', text: 'WRONG_LABEL', parent_ref: 'topic' },
      sendAck,
      hubRevision: 1,
    })

    expect(result.verified).toBe(false)
    expect(store.data?.nodes.length).toBe(beforeCount)
    expect(sendAck).toHaveBeenCalledWith(
      expect.objectContaining({
        verified: false,
        hub_persist_ok: false,
        error_code: 'verify_failed',
      })
    )
  })

  it('hub persist failure restores canvas and acks hub_persist_failed', async () => {
    const store = topicOnlyMindmapStore()
    const beforeCount = store.data?.nodes.length ?? 0
    const sendAck = vi.fn()

    vi.spyOn(hubPersistModule, 'persistVerifiedDiagramToHub').mockResolvedValue({
      ok: false,
      error: 'hub_persist_failed',
    })

    const result = await applyVerifiedDiagramUpdate('add_nodes', [{ text: 'DIY' }], {
      mutationId: 'mut-hub-fail',
      expectedEffect: { op: 'add_branch', text: 'DIY', parent_ref: 'topic' },
      sendAck,
      hubRevision: 1,
      hubPersist: {
        buildContext: () => ({
          diagram_type: 'mindmap',
          active_panel: 'one_sentence',
          selected_nodes: [],
          diagram_data: { children: [] },
        }),
        updateContext: vi.fn(),
        hubScopeRevision: 1,
      },
    })

    expect(result.verified).toBe(false)
    expect(result.verificationError).toBe('hub_persist_failed')
    expect(store.data?.nodes.length).toBe(beforeCount)
    expect(sendAck).toHaveBeenCalledWith(
      expect.objectContaining({
        error_code: 'hub_persist_failed',
        verified: false,
      })
    )
  })
})
