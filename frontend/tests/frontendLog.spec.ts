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

  it('skips benign ResizeObserver loop noise', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)

    reportFrontendError(
      new Error('ResizeObserver loop completed with undelivered notifications.'),
      { source: 'window.onerror' }
    )

    expect(fetch).not.toHaveBeenCalled()
  })

  it('skips opaque Script error noise', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)

    reportFrontendError('Script error.', { source: 'window.onerror' })
    reportFrontendError('Script error', { source: 'window.onerror' })

    expect(fetch).not.toHaveBeenCalled()
  })

  it('skips WeChat bridge postMessage noise', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)

    reportFrontendError(
      new Error("Cannot read properties of undefined (reading 'weixinPostMessageHandlers')"),
      { source: 'window.onerror' }
    )

    expect(fetch).not.toHaveBeenCalled()
  })

  it('skips injected browser script noise', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)

    const samples = [
      "null is not an object (evaluating 'e.childNodes')\ntraval",
      "null is not an object (evaluating 'document.querySelector('link[rel=\"shortcut icon\"]').getAttribute')",
      'UCShellJava.sdkEventFire is not a function',
      'ucapi is not defined',
      "Cannot read properties of undefined (reading 'LIDNotifyId')",
      'EmptyRanges',
      "Evaluating a string as JavaScript violates the following Content Security Policy directive because 'unsafe-eval' is not an allowed source of script: chrome-extension://abc",
      "Identifier 'Shop' has already been declared",
      'Unexpected end of input',
    ]
    for (const sample of samples) {
      reportFrontendError(new Error(sample), { source: 'window.onerror' })
    }

    expect(fetch).not.toHaveBeenCalled()
  })

  it('still reports app errors whose stack mentions an extension', () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)

    const err = new Error("Cannot read properties of null (reading 'offsetHeight')")
    err.stack =
      "TypeError: Cannot read properties of null (reading 'offsetHeight')\n" +
      '    at chrome-extension://abc/content.js:1:1\n' +
      '    at render (https://mg.example/assets/index-abc.js:1:2)'
    reportFrontendError(err, { source: 'vue' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('still reports Unexpected end of input when the stack is ours', () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)

    const err = new Error('Unexpected end of input')
    err.stack =
      'Error: Unexpected end of input\n    at parse (https://mg.example/assets/index-abc.js:1:2)'
    reportFrontendError(err, { source: 'window.onerror' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('does not skip generic offsetHeight layout errors', () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)

    reportFrontendError(new Error("Cannot read properties of null (reading 'offsetHeight')"), {
      source: 'vue',
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('skips stale chunk load errors from reporting', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)

    reportFrontendError(new Error('Failed to fetch dynamically imported module: https://x/a.js'), {
      source: 'unhandledrejection',
    })

    expect(fetch).not.toHaveBeenCalled()
  })

  it('skips AbortError / user-aborted fetch noise', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)

    const abort = new DOMException('The user aborted a request.', 'AbortError')
    reportFrontendError(abort, { source: 'unhandledrejection' })
    reportFrontendError(new Error('BodyStreamBuffer was aborted'), { source: 'unhandledrejection' })

    expect(fetch).not.toHaveBeenCalled()
  })
})
