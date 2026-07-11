/**
 * Desktop observer recovers from live_context after mobile hub persist event.
 * Owning-tab persist must not reload Pinia (SoT already applied).
 */
import { computed, ref } from 'vue'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import { applyKittyDiagramUpdate } from '@/composables/kitty/kittyAgentActions'
import { useKittyDesktopRemoteSync } from '@/composables/kitty/useKittyDesktopRemoteSync'

const { syncDiagramStoreFromVoiceContext } = vi.hoisted(() => ({
  syncDiagramStoreFromVoiceContext: vi.fn(),
}))

vi.mock('@/composables/kitty/syncDiagramStoreFromVoiceContext', () => ({
  syncDiagramStoreFromVoiceContext,
}))

vi.mock('@/composables/kitty/kittyAgentActions', () => ({
  applyKittyDiagramUpdate: vi.fn(),
}))

vi.mock('@/composables/kitty/kittyDiagramFingerprint', () => ({
  getKittyDiagramContentFingerprint: (data?: { nodes?: unknown[] } | null) => {
    const nodes = data?.nodes ?? []
    return nodes.length > 0 ? `hub-${nodes.length}` : 'local-empty'
  },
  getKittyVoiceDiagramFingerprint: () => 'remote-fp',
}))

vi.mock('@/composables/kitty/kittySelectionApply', () => ({
  applyKittyRemoteCanvasSelection: vi.fn(),
}))

vi.mock('@/composables/kitty/kittyDesktopMobileActiveHub', () => ({
  acquireKittyMobileActiveHub: () => () => undefined,
  isKittyMobileActiveHubFresh: () => true,
  useKittyMobileActiveHubSnapshot: () =>
    ref({
      active: true,
      scopes: ['lib-1'],
      primaryScope: 'lib-1',
      updatedAt: Date.now(),
    }),
}))

vi.mock('@/stores/diagram', () => ({
  useDiagramStore: () => ({
    type: 'mindmap',
    data: { nodes: [], connections: [] },
  }),
}))

describe('useKittyDesktopRemoteSync hub persist recovery', () => {
  beforeEach(() => {
    syncDiagramStoreFromVoiceContext.mockClear()
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
})
