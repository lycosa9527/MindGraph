/**
 * Canvas owner must clear ownsKittySession when disabled or scope emptied.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { computed, effectScope, nextTick, ref } from 'vue'

const { startConversation, stopConversation, isConnected, isLiveForScope } = vi.hoisted(() => {
  const isConnected = { value: false }
  return {
    startConversation: vi.fn(async () => {
      isConnected.value = true
    }),
    stopConversation: vi.fn(async () => {
      isConnected.value = false
    }),
    isConnected,
    isLiveForScope: vi.fn(() => true),
  }
})

vi.mock('@/composables/kitty/useKittyAgent', () => ({
  useKittyAgent: () => ({
    startConversation,
    stopConversation,
    isConnected,
    isLiveForScope,
    updateContext: vi.fn(),
    registerDiagramContextBuilder: vi.fn(),
    state: { value: 'idle' },
  }),
}))

vi.mock('@/composables/kitty/pipeline/hubSyncWorker', () => ({
  runKittyHubSync: vi.fn(async () => ({ ok: true, revision: 1 })),
}))

vi.mock('@/composables/kitty/buildKittyDiagramContext', () => ({
  buildKittyDiagramContext: () => ({
    diagram_type: 'mindmap',
    active_panel: 'none',
    selected_nodes: [],
    diagram_data: {},
  }),
}))

vi.mock('@/stores/diagram', () => ({
  useDiagramStore: () => ({ type: 'mindmap', data: { nodes: [], connections: [] } }),
}))

vi.mock('@/stores/oneSentence', () => ({
  useOneSentenceStore: () => ({ phase: 'edit' }),
}))

vi.mock('@/composables/core/useEventBus', () => ({
  eventBus: {
    onWithOwner: vi.fn(),
    removeAllListenersForOwner: vi.fn(),
    emit: vi.fn(),
  },
}))

import { useKittyCanvasOwnerAgent } from '@/composables/kitty/useKittyCanvasOwnerAgent'
import { useKittySessionStore } from '@/stores/kittySession'

describe('useKittyCanvasOwnerAgent ownership reset', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    startConversation.mockClear()
    stopConversation.mockClear()
    isConnected.value = false
    isLiveForScope.mockReturnValue(true)
  })

  it('clears ownsKittySession when enabled becomes false', async () => {
    const scope = ref<string | null>('lib-1')
    const enabled = ref(true)
    const scopeRun = effectScope()
    scopeRun.run(() => {
      useKittyCanvasOwnerAgent({
        libraryDiagramId: scope,
        enabled: computed(() => enabled.value),
      })
    })
    await nextTick()
    await Promise.resolve()
    expect(useKittySessionStore().ownsKittySession).toBe(true)

    enabled.value = false
    await nextTick()
    expect(useKittySessionStore().ownsKittySession).toBe(false)
    expect(stopConversation).toHaveBeenCalled()
    scopeRun.stop()
  })

  it('clears ownsKittySession when scope becomes empty', async () => {
    const scope = ref<string | null>('lib-1')
    const enabled = ref(true)
    const scopeRun = effectScope()
    scopeRun.run(() => {
      useKittyCanvasOwnerAgent({
        libraryDiagramId: scope,
        enabled: computed(() => enabled.value),
      })
    })
    await nextTick()
    await Promise.resolve()
    expect(useKittySessionStore().ownsKittySession).toBe(true)

    scope.value = null
    await nextTick()
    expect(useKittySessionStore().ownsKittySession).toBe(false)
    expect(stopConversation).toHaveBeenCalled()
    scopeRun.stop()
  })
})
