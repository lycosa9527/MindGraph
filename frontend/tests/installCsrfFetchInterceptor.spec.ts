import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { __testing, installCsrfFetchInterceptor } from '@/utils/installCsrfFetchInterceptor'

function setCookie(value: string): void {
  Object.defineProperty(document, 'cookie', {
    configurable: true,
    get: () => value,
  })
}

describe('installCsrfFetchInterceptor', () => {
  let originalFetch: typeof window.fetch

  beforeEach(() => {
    originalFetch = window.fetch
  })

  afterEach(() => {
    __testing.resetForTests()
    window.fetch = originalFetch
    vi.restoreAllMocks()
  })

  function captureHeaders(): { calls: Array<Headers | undefined> } {
    const calls: Array<Headers | undefined> = []
    window.fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const headers = init?.headers
        ? new Headers(init.headers as HeadersInit)
        : input instanceof Request
          ? input.headers
          : undefined
      calls.push(headers)
      return Promise.resolve(new Response('{}', { status: 200 }))
    }) as typeof window.fetch
    installCsrfFetchInterceptor()
    return { calls }
  }

  it('adds X-CSRF-Token to same-origin mutations when cookie present', async () => {
    setCookie('csrf_token=tok-123')
    const { calls } = captureHeaders()
    await window.fetch('/api/conversations/rename', { method: 'POST' })
    expect(calls[0]?.get('X-CSRF-Token')).toBe('tok-123')
  })

  it('does not add header to GET requests', async () => {
    setCookie('csrf_token=tok-123')
    const { calls } = captureHeaders()
    await window.fetch('/api/conversations', { method: 'GET' })
    expect(calls[0]?.get('X-CSRF-Token') ?? null).toBeNull()
  })

  it('overwrites a stale token with the current cookie value', async () => {
    setCookie('csrf_token=fresh-token')
    const { calls } = captureHeaders()
    await window.fetch('/api/auth/refresh', {
      method: 'POST',
      headers: { 'X-CSRF-Token': 'stale-token' },
    })
    expect(calls[0]?.get('X-CSRF-Token')).toBe('fresh-token')
  })

  it('skips cross-origin requests', async () => {
    setCookie('csrf_token=tok-123')
    const { calls } = captureHeaders()
    await window.fetch('https://other.example.com/api/x', { method: 'POST' })
    expect(calls[0]?.get('X-CSRF-Token') ?? null).toBeNull()
  })

  it('is a no-op when no csrf cookie exists', async () => {
    setCookie('')
    const { calls } = captureHeaders()
    await window.fetch('/api/conversations/rename', { method: 'POST' })
    expect(calls[0]?.get('X-CSRF-Token') ?? null).toBeNull()
  })
})
