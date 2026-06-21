import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  reportFrontendError,
  resetFrontendLogDedupeForTests,
  shouldSkipFrontendReportingForTests,
} from '@/utils/frontendLog'

describe('frontendLog', () => {
  afterEach(() => {
    resetFrontendLogDedupeForTests()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('skips reporting in development', () => {
    expect(shouldSkipFrontendReportingForTests()).toBe(true)
  })

  it('dedupes identical errors within the window', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)

    reportFrontendError(new Error('same failure'), { source: 'test' })
    reportFrontendError(new Error('same failure'), { source: 'test' })

    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('formats error messages with source and path', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)

    reportFrontendError(new Error('boom'), { source: 'vue', info: 'render' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    const body = JSON.parse(String(init.body)) as { level: string; message: string; source: string }
    expect(body.level).toBe('error')
    expect(body.source).toBe('vue')
    expect(body.message).toContain('boom')
    expect(body.message).toContain('source=vue')
  })
})
