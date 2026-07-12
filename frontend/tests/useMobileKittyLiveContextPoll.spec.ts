/**
 * Mobile live_context poll hydrates Pinia when linked.
 */
import { computed, ref } from 'vue'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const syncMock = vi.hoisted(() => vi.fn(() => true))
const applySelectionMock = vi.hoisted(() => vi.fn())
const applyLlmMock = vi.hoisted(() => vi.fn(async () => false))
const hydrateLibraryMock = vi.hoisted(() => vi.fn(async () => true))

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

vi.mock('@/stores/diagram', () => ({
  useDiagramStore: () => ({
    selectedNodes: [] as string[],
  }),
}))

import { useMobileKittyLiveContextPoll } from '@/composables/kitty/useMobileKittyLiveContextPoll'

describe('useMobileKittyLiveContextPoll', () => {
  beforeEach(() => {
    syncMock.mockClear()
    applySelectionMock.mockClear()
    applyLlmMock.mockClear()
    hydrateLibraryMock.mockClear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('hydrates diagram from live_context when linked', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
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
      }))
    )

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

    expect(syncMock).toHaveBeenCalled()
    expect(applySelectionMock).toHaveBeenCalledWith(['topic'], { canvasHighlight: false })
    expect(applyLlmMock).toHaveBeenCalledWith('qwen')
  })

  it('skips while edit pipeline is active', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    useMobileKittyLiveContextPoll({
      libraryDiagramId: computed(() => 'lib-1'),
      enabled: computed(() => true),
      editPipelineActive: computed(() => true),
    })

    await vi.advanceTimersByTimeAsync(0)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
