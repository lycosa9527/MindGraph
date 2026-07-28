/**
 * Mobile live_context poll hydrates Pinia when linked.
 */
import { computed, ref } from 'vue'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const syncMock = vi.hoisted(() => vi.fn(() => true))
const applySelectionMock = vi.hoisted(() => vi.fn())
const applyLlmMock = vi.hoisted(() => vi.fn(async () => false))
const hydrateLibraryMock = vi.hoisted(() => vi.fn(async () => true))
const apiRequestMock = vi.hoisted(() => vi.fn())

vi.mock('@/composables/kitty/syncDiagramStoreFromVoiceContext', () => ({
  syncDiagramStoreFromVoiceContext: syncMock,
}))

vi.mock('@/composables/kitty/kittySelectionApply', () => ({
  applyKittyRemoteCanvasSelection: applySelectionMock,
}))

vi.mock('@/composables/kitty/applyKittyRemoteLlmModel', () => ({
  applyKittyRemoteLlmModel: applyLlmMock,
}))

vi.mock('@/composables/kitty/hydrateMobileKittyFromLibrary', () => ({
  hydrateMobileKittyFromLibrary: hydrateLibraryMock,
}))

vi.mock('@/utils/apiClient', () => ({
  apiRequest: (...args: unknown[]) => apiRequestMock(...args),
}))

vi.mock('@/stores/diagram', () => ({
  useDiagramStore: () => ({
    selectedNodes: [] as string[],
  }),
}))

import { useMobileKittyLiveContextPoll } from '@/composables/kitty/useMobileKittyLiveContextPoll'

describe('useMobileKittyLiveContextPoll', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    syncMock.mockClear()
    applySelectionMock.mockClear()
    applyLlmMock.mockClear()
    hydrateLibraryMock.mockClear()
    apiRequestMock.mockReset()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('hydrates diagram from live_context when linked', async () => {
    apiRequestMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        ok: true,
        updated_at: 100,
        diagram_type: 'mindmap',
        diagram_data: {
          nodes: [{ id: 'topic', text: 'Hello' }],
          connections: [],
        },
        selected_nodes: ['topic'],
        selected_llm_model: 'qwen',
      }),
    })

    const libraryDiagramId = ref<string | null>('lib-1')
    const editPipelineActive = ref(false)
    useMobileKittyLiveContextPoll({
      libraryDiagramId,
      enabled: computed(() => true),
      editPipelineActive,
    })

    await vi.advanceTimersByTimeAsync(0)
    await Promise.resolve()
    await Promise.resolve()

    expect(apiRequestMock).toHaveBeenCalledWith(
      '/api/kitty/live_context/lib-1',
      expect.objectContaining({ method: 'GET' })
    )
    expect(syncMock).toHaveBeenCalled()
    expect(applySelectionMock).toHaveBeenCalledWith(['topic'], { canvasHighlight: false })
    expect(applyLlmMock).toHaveBeenCalledWith('qwen')
  })

  it('skips while edit pipeline is active', async () => {
    useMobileKittyLiveContextPoll({
      libraryDiagramId: computed(() => 'lib-1'),
      enabled: computed(() => true),
      editPipelineActive: computed(() => true),
    })

    await vi.advanceTimersByTimeAsync(0)
    expect(apiRequestMock).not.toHaveBeenCalled()
  })
})
