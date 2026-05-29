/**
 * Desktop Kitty live sync applies selection metadata only — never loadFromSpec.
 */
import { computed, ref } from 'vue'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useKittyDesktopLiveSpecSync } from '@/composables/kitty/useKittyDesktopLiveSpecSync'

const { loadFromSpec, selectNodes, clearSelection } = vi.hoisted(() => ({
  loadFromSpec: vi.fn(),
  selectNodes: vi.fn(),
  clearSelection: vi.fn(),
}))

vi.mock('@/stores/diagram', () => ({
  useDiagramStore: () => ({
    type: 'circle_map',
    loadFromSpec,
    selectNodes,
    clearSelection,
  }),
}))

vi.mock('@/composables/kitty/syncDiagramStoreFromVoiceContext', () => ({
  syncDiagramStoreFromVoiceContext: vi.fn(),
}))

vi.mock('@/composables/kitty/kittyAgentActions', () => ({
  applyKittyDiagramUpdate: vi.fn(),
}))

vi.mock('@/composables/kitty/kittyDiagramFingerprint', () => ({
  getKittyDiagramContentFingerprint: () => 'local-fp',
  getKittyVoiceDiagramFingerprint: () => 'voice-fp',
}))

vi.mock('@/composables/kitty/kittySelectionApply', () => ({
  applyKittyRemoteCanvasSelection: (nodes: string[]) => {
    if (nodes.length > 0) {
      selectNodes(nodes)
    } else {
      clearSelection()
    }
  },
}))

vi.mock('@/composables/kitty/kittyDesktopMobileActiveHub', () => ({
  acquireKittyMobileActiveHub: () => () => undefined,
  isKittyMobileActiveHubFresh: () => false,
  useKittyMobileActiveHubSnapshot: () =>
    ref({
      active: false,
      updatedAt: 0,
    }),
}))

describe('useKittyDesktopLiveSpecSync', () => {
  beforeEach(() => {
    loadFromSpec.mockClear()
    selectNodes.mockClear()
    clearSelection.mockClear()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ok: true,
          updated_at: 100,
          diagram_type: 'circle_map',
          diagram_data: { topic: 'wrong', context: ['bad'] },
          selected_nodes: ['context-0'],
        }),
      })
    )
  })

  it('syncs selected_nodes without calling loadFromSpec', async () => {
    const { refresh } = useKittyDesktopLiveSpecSync({
      libraryDiagramId: ref('lib-1'),
      syncEnabled: computed(() => true),
      collabSessionActive: computed(() => false),
    })

    await refresh()

    expect(loadFromSpec).not.toHaveBeenCalled()
    expect(selectNodes).toHaveBeenCalledWith(['context-0'])
  })
})
