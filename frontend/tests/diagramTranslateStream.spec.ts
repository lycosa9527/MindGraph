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
})
