import { describe, expect, it, vi } from 'vitest'

import { consumeDiagramTranslateNdjsonStream } from '@/utils/diagramTranslateStream'

describe('consumeDiagramTranslateNdjsonStream', () => {
  it('does not report an error when the reader aborts', async () => {
    const onError = vi.fn()
    const onItem = vi.fn()
    const aborted = new Error('Aborted')
    aborted.name = 'AbortError'
    const response = {
      body: {
        getReader: () => ({
          read: async () => {
            throw aborted
          },
        }),
      },
    } as unknown as Response

    await consumeDiagramTranslateNdjsonStream(response, {
      onItem,
      onError,
    })

    expect(onError).not.toHaveBeenCalled()
    expect(onItem).not.toHaveBeenCalled()
  })

  it('forwards thinking_coin_insufficient from an error event', async () => {
    const onError = vi.fn()
    const payload = JSON.stringify({
      event: 'error',
      detail: 'short',
      error_type: 'thinking_coin_insufficient',
    })
    let reads = 0
    const response = {
      body: {
        getReader: () => ({
          read: async () => {
            reads += 1
            if (reads === 1) {
              return { done: false, value: new TextEncoder().encode(`${payload}\n`) }
            }
            return { done: true, value: undefined }
          },
        }),
      },
    } as unknown as Response

    await consumeDiagramTranslateNdjsonStream(response, {
      onItem: vi.fn(),
      onError,
    })

    expect(onError).toHaveBeenCalledWith('short', 'thinking_coin_insufficient')
  })
})
