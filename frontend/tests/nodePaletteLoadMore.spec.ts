import { ref } from 'vue'

import { describe, expect, it, vi } from 'vitest'

import { streamNodePaletteBatch } from '@/composables/nodePalette/streamNodePaletteBatch'
import type { NodePaletteStreamDeps } from '@/composables/nodePalette/streamNodePaletteBatch'
import type { NodeSuggestion } from '@/types/panels'

const authFetchMock = vi.hoisted(() => vi.fn())

vi.mock('@/utils/api', () => ({
  authFetch: authFetchMock,
}))

vi.mock('@/fonts/promptLanguageFonts', () => ({
  ensureFontsForLanguageCode: vi.fn(async () => undefined),
}))

vi.mock('@/stores/savedDiagrams', () => ({
  useSavedDiagramsStore: () => ({ activeDiagramId: null }),
}))

function sseResponse(body: string): Response {
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

function nodeEvent(id: string, text: string): string {
  return `data: ${JSON.stringify({ event: 'node_generated', node: { id, text } })}\n\n`
}

function deps(initial: NodeSuggestion[]): {
  streamDeps: NodePaletteStreamDeps
  items: () => NodeSuggestion[]
} {
  let suggestions = initial.slice()
  const streamDeps: NodePaletteStreamDeps = {
    panelsStore: {} as NodePaletteStreamDeps['panelsStore'],
    promptLanguage: ref('zh'),
    abortController: ref(null),
    paletteActiveControllers: ref([]),
    paletteStreamSession: ref(null),
    errorMessage: ref(null),
    paletteStreamPhase: ref('idle'),
    streamBatchDepth: { value: 0 },
    firstNodeReceivedInBatch: { value: false },
    suggestionSink: {
      getSuggestions: () => suggestions,
      clearSuggestions: () => {
        suggestions = []
      },
      appendSuggestion: (suggestion) => {
        suggestions = [...suggestions, suggestion]
      },
    },
  }
  return { streamDeps, items: () => suggestions }
}

describe('node palette load more', () => {
  it('keeps earlier suggestions when the next batch appends', async () => {
    authFetchMock.mockReset()
    authFetchMock.mockResolvedValue(sseResponse(`${nodeEvent('new-1', 'later')}`))
    const previous: NodeSuggestion = { id: 'old-1', text: 'earlier', type: 'bubble' }
    const { streamDeps, items } = deps([previous])

    await streamNodePaletteBatch(
      streamDeps,
      '/thinking_mode/node_palette/next_batch',
      {},
      {
        append: true,
      }
    )

    expect(items().map((item) => item.id)).toEqual(['old-1', 'new-1'])
    expect(items()[0]?.text).toBe('earlier')
  })

  it('replaces the list when a fresh session does not append', async () => {
    authFetchMock.mockReset()
    authFetchMock.mockResolvedValue(sseResponse(`${nodeEvent('new-1', 'later')}`))
    const previous: NodeSuggestion = { id: 'old-1', text: 'earlier', type: 'bubble' }
    const { streamDeps, items } = deps([previous])

    await streamNodePaletteBatch(streamDeps, '/thinking_mode/node_palette/start', {})

    expect(items().map((item) => item.id)).toEqual(['new-1'])
  })
})
