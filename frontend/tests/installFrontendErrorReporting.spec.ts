import { createApp, defineComponent } from 'vue'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { installFrontendErrorReporting } from '@/utils/installFrontendErrorReporting'

const reportMock = vi.hoisted(() => vi.fn())

vi.mock('@/utils/frontendLog', () => ({
  reportFrontendError: (...args: unknown[]) => reportMock(...args),
}))

vi.mock('@/utils/staleChunkReload', () => ({
  reloadForStaleChunk: () => false,
}))

describe('installFrontendErrorReporting', () => {
  beforeEach(() => {
    reportMock.mockReset()
  })

  it('returns when the vue error handler re-enters', () => {
    const app = createApp(
      defineComponent({
        setup() {
          return () => null
        },
      })
    )
    installFrontendErrorReporting(app)
    const handler = app.config.errorHandler
    expect(handler).toBeTypeOf('function')
    reportMock.mockImplementation(() => {
      handler?.(new Error('nested'), null, 'render')
    })
    handler?.(new Error('first'), null, 'render')
    expect(reportMock).toHaveBeenCalledTimes(1)
  })
})
