/**
 * Desktop observer recovers from live_context after mobile hub persist event.
 * Owning-tab Pinia must never be reloaded from stale Redis (branch loss bug).
 */
import { computed, ref } from 'vue'

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import { applyKittyDiagramUpdate } from '@/composables/kitty/kittyAgentActions'
import { useKittyDesktopRemoteSync } from '@/composables/kitty/useKittyDesktopRemoteSync'
import { useKittySessionStore } from '@/stores/kittySession'

const { syncDiagramStoreFromVoiceContext, runKittyHubSyncMock, localNodes } = vi.hoisted(() => ({
  syncDiagramStoreFromVoiceContext: vi.fn(),
  runKittyHubSyncMock: vi.fn(async () => ({ ok: true, revision: 1 })),
  localNodes: { value: [] as { id: string; text: string }[] },
}))

vi.mock('@/composables/kitty/syncDiagramStoreFromVoiceContext', () => ({
  syncDiagramStoreFromVoiceContext,
}))

vi.mock('@/composables/kitty/pipeline/hubSyncWorker', () => ({
  runKittyHubSync: runKittyHubSyncMock,
}))

vi.mock('@/composables/kitty/kittyAgentActions', () => ({
  applyKittyDiagramUpdate: vi.fn(),
  executeKittyAgentAction: vi.fn(),
}))

vi.mock('@/composables/kitty/kittyDiagramFingerprint', () => ({
  getKittyDiagramContentFingerprint: (data?: { nodes?: unknown[] } | null) => {
    const nodes = data?.nodes ?? []
    return nodes.length > 0 ? `fp-${nodes.length}` : 'local-empty'
  },
  getKittyVoiceDiagramFingerprint: () => 'remote-fp',
}))

vi.mock('@/composables/kitty/kittySelectionApply', () => ({
  applyKittyRemoteCanvasSelection: vi.fn(),
}))

vi.mock('@/composables/kitty/applyKittyRemoteLlmModel', () => ({
  applyKittyRemoteLlmModel: vi.fn(),
}))

vi.mock('@/composables/kitty/kittyDesktopMobileActiveHub', () => ({
  acquireKittyMobileActiveHub: () => () => undefined,
  isKittyMobileActiveHubFresh: () => false,
  useKittyMobileActiveHubSnapshot: () =>
    ref({
      active: false,
      scopes: [] as string[],
      primaryScope: null,
      updatedAt: 0,
    }),
}))

vi.mock('@/composables/kitty/kittyWorkflowTrace', () => ({
  traceKittyWorkflow: vi.fn(),
}))

vi.mock('@/stores/diagram', () => ({
  useDiagramStore: () => ({
    type: 'mindmap',
    get data() {
      return { nodes: localNodes.value, connections: [] }
    },
    collabSessionActive: false,
  }),
}))

describe('useKittyDesktopRemoteSync hub persist recovery', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localNodes.value = []
    syncDiagramStoreFromVoiceContext.mockClear()
    runKittyHubSyncMock.mockClear()
    eventBus.removeAllListenersForOwner('KittyDesktopRemoteSync')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ok: true,
          updated_at: 200,
          diagram_type: 'mindmap',
          diagram_data: {
            center: { text: 'Cars' },
            children: [{ text: 'DIY' }],
            nodes: [{ id: 'topic', text: 'Cars' }],
            connections: [],
          },
          selected_nodes: [],
        }),
      })
    )
  })

  it('does not reload Pinia when owning_tab emits kitty:hub_diagram_persisted', async () => {
    useKittyDesktopRemoteSync({
      libraryDiagramId: ref('lib-1'),
      syncEnabled: computed(() => true),
      collabSessionActive: computed(() => false),
    })

    eventBus.emit('kitty:hub_diagram_persisted', {
      scope: 'lib-1',
      revision: 12,
      source: 'owning_tab',
    })
    await new Promise((r) => setTimeout(r, 50))

    expect(syncDiagramStoreFromVoiceContext).not.toHaveBeenCalled()
  })

  it('does not apply diagram fanout when mutation_id is present', () => {
    vi.mocked(applyKittyDiagramUpdate).mockClear()

    useKittyDesktopRemoteSync({
      libraryDiagramId: ref('lib-1'),
      syncEnabled: computed(() => true),
      collabSessionActive: computed(() => false),
    })

    eventBus.emit('kitty:desktop_diagram_update', {
      scope: 'lib-1',
      action: 'add_nodes',
      updates: [{ text: 'DIY' }],
      mutation_id: 'mut-abc',
    })

    expect(applyKittyDiagramUpdate).not.toHaveBeenCalled()
  })

  it('forces live_context poll for observer hub persist (no owning_tab source)', async () => {
    useKittyDesktopRemoteSync({
      libraryDiagramId: ref('lib-1'),
      syncEnabled: computed(() => true),
      collabSessionActive: computed(() => false),
    })

    eventBus.emit('kitty:hub_diagram_persisted', { scope: 'lib-1', revision: 12 })
    await new Promise((r) => setTimeout(r, 50))

    expect(fetch).toHaveBeenCalled()
    expect(syncDiagramStoreFromVoiceContext).toHaveBeenCalled()
  })

  it('does not clobber Pinia from live_context when ownsKittySession', async () => {
    useKittySessionStore().setOwnsKittySession(true)
    localNodes.value = [
      { id: 'topic', text: 'Cars' },
      { id: 'branch-1', text: 'DIY' },
      { id: 'child-1', text: 'Paint' },
    ]

    const sync = useKittyDesktopRemoteSync({
      libraryDiagramId: ref('lib-1'),
      syncEnabled: computed(() => true),
      collabSessionActive: computed(() => false),
    })
    await sync.refresh()

    expect(syncDiagramStoreFromVoiceContext).not.toHaveBeenCalled()
  })

  it('does not regress richer local Pinia to smaller hub snapshot', async () => {
    useKittySessionStore().setOwnsKittySession(false)
    localNodes.value = [
      { id: 'topic', text: 'Cars' },
      { id: 'branch-1', text: 'DIY' },
      { id: 'child-1', text: 'Paint' },
    ]

    const sync = useKittyDesktopRemoteSync({
      libraryDiagramId: ref('lib-1'),
      syncEnabled: computed(() => true),
      collabSessionActive: computed(() => false),
    })
    await sync.refresh()

    expect(syncDiagramStoreFromVoiceContext).not.toHaveBeenCalled()
  })

  it('does not re-run hub sync after autocomplete (verified path already persisted)', async () => {
    useKittySessionStore().setOwnsKittySession(true)
    useKittyDesktopRemoteSync({
      libraryDiagramId: ref('lib-1'),
      syncEnabled: computed(() => true),
      collabSessionActive: computed(() => false),
      hubPersist: {
        buildContext: () =>
          ({
            diagram_type: 'mindmap',
            active_panel: 'none',
            selected_nodes: [],
            diagram_data: {},
          }) as never,
        updateContext: vi.fn(),
      },
    })

    eventBus.emit('kitty:diagram_action_completed', {
      action: 'auto_complete_branch',
      ok: true,
      userSummary: 'ok',
    })
    await new Promise((r) => setTimeout(r, 50))

    expect(runKittyHubSyncMock).not.toHaveBeenCalled()
  })
})
