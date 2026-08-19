import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/utils/sessionRefresh', () => ({
  refreshSessionAccessToken: vi.fn(),
  getSessionRefreshEpoch: vi.fn(() => 0),
  ensureFreshSessionAfterAuthFailure: vi.fn(async () => false),
}))

import { useAuthStore } from '@/stores/auth'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function memoryStorage(): Storage {
  const map = new Map<string, string>()
  return {
    get length() {
      return map.size
    },
    clear: () => map.clear(),
    getItem: (key: string) => map.get(key) ?? null,
    key: (index: number) => [...map.keys()][index] ?? null,
    removeItem: (key: string) => {
      map.delete(key)
    },
    setItem: (key: string, value: string) => {
      map.set(key, value)
    },
  }
}

function meCallCount(fetchMock: ReturnType<typeof vi.fn>): number {
  return fetchMock.mock.calls.filter((call) => String(call[0]).includes('/api/auth/me'))
    .length
}

function capabilitiesCallCount(fetchMock: ReturnType<typeof vi.fn>): number {
  return fetchMock.mock.calls.filter((call) =>
    String(call[0]).includes('/api/auth/admin/capabilities')
  ).length
}

const meUser = {
  id: 1,
  phone: '100',
  name: 'admin',
  role: 'superadmin',
  ui_language: 'en',
  prompt_language: 'en',
  match_prompt_to_ui: true,
}

const capsBody = {
  role: 'superadmin',
  capabilities: ['scope.global', 'tab.data_center.view'],
  org_ids: null,
  read_only: false,
  default_org_id: null,
  panel_access: true,
  showcase_permissions: [],
}

describe('auth bootstrap dedupe', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', memoryStorage())
    vi.stubGlobal('sessionStorage', memoryStorage())
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('does not re-fetch /me on immediate session-monitor kick after checkAuth', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/auth/me')) {
        return jsonResponse({ user: meUser })
      }
      if (url.includes('/api/auth/admin/capabilities')) {
        return jsonResponse(capsBody)
      }
      if (url.includes('/api/auth/session-status')) {
        return jsonResponse({ status: 'active', token: 't' })
      }
      if (url.includes('/api/auth/language-preferences')) {
        return jsonResponse({ ok: true })
      }
      return jsonResponse({})
    })
    vi.stubGlobal('fetch', fetchMock)

    const authStore = useAuthStore()
    const ok = await authStore.checkAuth()
    expect(ok).toBe(true)
    expect(meCallCount(fetchMock)).toBe(1)
    expect(
      fetchMock.mock.calls.some((call) => String(call[0]).includes('/api/auth/session-status'))
    ).toBe(true)
  })

  it('skips capabilities refetch within TTL unless force', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/auth/me')) {
        return jsonResponse({ user: meUser })
      }
      if (url.includes('/api/auth/admin/capabilities')) {
        return jsonResponse(capsBody)
      }
      if (url.includes('/api/auth/session-status')) {
        return jsonResponse({ status: 'active', token: 't' })
      }
      if (url.includes('/api/auth/language-preferences')) {
        return jsonResponse({ ok: true })
      }
      return jsonResponse({})
    })
    vi.stubGlobal('fetch', fetchMock)

    const authStore = useAuthStore()
    await authStore.checkAuth()
    await authStore.loadAdminCapabilities()
    expect(capabilitiesCallCount(fetchMock)).toBe(1)

    // Mimics AdminPage/sidebar loadCapabilities() after router force/entry.
    await authStore.loadAdminCapabilities()
    expect(capabilitiesCallCount(fetchMock)).toBe(1)

    await authStore.loadAdminCapabilities({ force: true })
    expect(capabilitiesCallCount(fetchMock)).toBe(2)
  })

  it('does not poll /me on the kick-check interval', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/auth/me')) {
        return jsonResponse({ user: meUser })
      }
      if (url.includes('/api/auth/admin/capabilities')) {
        return jsonResponse(capsBody)
      }
      if (url.includes('/api/auth/session-status')) {
        return jsonResponse({ status: 'active', token: 't' })
      }
      return jsonResponse({})
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })

    const authStore = useAuthStore()
    expect(await authStore.checkAuth()).toBe(true)
    await Promise.resolve()
    await Promise.resolve()
    const meAfterAuth = meCallCount(fetchMock)
    const sessionAfterAuth = fetchMock.mock.calls.filter((call) =>
      String(call[0]).includes('/api/auth/session-status')
    ).length

    await vi.advanceTimersByTimeAsync(120_000)
    await Promise.resolve()
    await Promise.resolve()

    expect(meCallCount(fetchMock)).toBe(meAfterAuth)
    expect(
      fetchMock.mock.calls.filter((call) => String(call[0]).includes('/api/auth/session-status'))
        .length
    ).toBeGreaterThan(sessionAfterAuth)

    authStore.stopSessionMonitoring()
  })
})
