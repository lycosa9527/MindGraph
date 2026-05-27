/**
 * Hub persist waits for context_mutation_ack before advancing fingerprint.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, ref } from 'vue'

const { getDiagramSpec, onWithOwnerMock, removeAllListenersForOwnerMock } = vi.hoisted(() => ({
  getDiagramSpec: vi.fn(() => ({ topic: 'A', context: ['b'] })),
  onWithOwnerMock: vi.fn(),
  removeAllListenersForOwnerMock: vi.fn(),
}))

vi.mock('@/composables/editor/useDiagramSpecForSave', () => ({
  useDiagramSpecForSave: () => getDiagramSpec,
}))

vi.mock('@/composables/core/useLanguage', () => ({
  useLanguage: () => ({ promptLanguage: ref('zh') }),
}))

vi.mock('@/composables/core/useEventBus', () => ({
  eventBus: {
    onWithOwner: onWithOwnerMock,
    removeAllListenersForOwner: removeAllListenersForOwnerMock,
  },
}))

vi.mock('@/stores/diagram', () => ({
  useDiagramStore: () => ({
    type: 'circle_map',
    data: {
      nodes: [{ id: 'topic', text: 'A' }],
      connections: [],
    },
  }),
}))

vi.mock('@/config', () => ({
  SAVE: { AUTO_SAVE_DEBOUNCE_MS: 2000 },
}))

import { useKittyMobileHubPersist } from '@/composables/kitty/useKittyMobileHubPersist'

describe('useKittyMobileHubPersist', () => {
  beforeEach(() => {
    getDiagramSpec.mockClear()
    onWithOwnerMock.mockClear()
    removeAllListenersForOwnerMock.mockClear()
  })

  it('sends persist payload and advances fingerprint only after ack', () => {
    const updateContext = vi.fn()
    const { flushHubLibraryPersist } = useKittyMobileHubPersist({
      libraryDiagramId: computed(() => 'lib-abc'),
      diagramDisplayTitle: computed(() => 'Title'),
      isConnected: ref(true),
      buildContext: () => ({
        diagram_type: 'circle_map',
        active_panel: 'none',
        selected_nodes: [],
        diagram_data: {},
        diagram_library_id: 'lib-abc',
      }),
      updateContext,
    })

    expect(onWithOwnerMock).toHaveBeenCalledWith(
      'voice:context_mutation_ack',
      expect.any(Function),
      'KittyMobileHubPersist'
    )

    flushHubLibraryPersist()
    expect(updateContext).toHaveBeenCalledTimes(1)
    expect(updateContext.mock.calls[0][1]?.persistLibrary).toBe(true)

    flushHubLibraryPersist()
    expect(updateContext).toHaveBeenCalledTimes(1)

    const ackHandler = onWithOwnerMock.mock.calls.find(
      (call) => call[0] === 'voice:context_mutation_ack'
    )?.[1] as
      | ((data: {
          ok?: boolean
          idempotency_key?: string
          persist_library?: boolean
          library_snapshot_saved?: boolean
        }) => void)
      | undefined

    expect(ackHandler).toBeDefined()
    const idemKey = updateContext.mock.calls[0][1]?.idempotencyKey as string
    ackHandler?.({
      ok: true,
      idempotency_key: idemKey,
      persist_library: true,
      library_snapshot_saved: true,
    })

    flushHubLibraryPersist()
    expect(updateContext).toHaveBeenCalledTimes(1)
  })
})
