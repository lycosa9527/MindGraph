import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/utils/sessionRefresh', () => ({
  refreshSessionAccessToken: vi.fn(),
}))

import { refreshSessionAccessToken } from '@/utils/sessionRefresh'
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

function capabilitiesCallCount(fetchMock: ReturnType<typeof vi.fn>): number {
  return fetchMock.mock.calls.filter((call) =>
    String(call[0]).includes('/api/auth/admin/capabilities')
  ).length
}

describe('loadAdminCapabilities', () => {
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
    vi.mocked(refreshSessionAccessToken).mockReset()
  })

  it('does not fetch before the session is verified this tab', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const authStore = useAuthStore()
    // Direct assign: sessionStorage restore path (unverified).
    authStore.user = {
      id: '1',
      username: 'admin',
      phone: '100',
      role: 'superadmin',
      avatar: '🙂',
    }

    await authStore.loadAdminCapabilities()

    expect(capabilitiesCallCount(fetchMock)).toBe(0)
    expect(authStore.adminCapabilitiesLoaded).toBe(false)
    expect(authStore.adminCapabilitiesPayload).toBeNull()
  })

  it('retries once after access-token refresh on 401', async () => {
    const capsBody = {
      role: 'superadmin',
      capabilities: ['scope.global', 'tab.data_center.view'],
      org_ids: null,
      read_only: false,
      default_org_id: null,
      panel_access: true,
      showcase_permissions: [],
    }
    let capabilitiesHits = 0
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/auth/me')) {
        return jsonResponse({
          user: {
            id: 1,
            phone: '100',
            name: 'admin',
            role: 'superadmin',
            ui_language: 'en',
            prompt_language: 'en',
            match_prompt_to_ui: true,
          },
        })
      }
      if (url.includes('/api/auth/admin/capabilities')) {
        capabilitiesHits += 1
        if (capabilitiesHits === 1) {
          return jsonResponse({ detail: 'JWT token required' }, 401)
        }
        return jsonResponse(capsBody)
      }
      if (url.includes('/api/auth/language-preferences')) {
        return jsonResponse({ ok: true })
      }
      return jsonResponse({})
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.mocked(refreshSessionAccessToken).mockResolvedValue(true)

    const authStore = useAuthStore()
    const ok = await authStore.checkAuth()
    expect(ok).toBe(true)
    expect(authStore.isAuthSessionVerified).toBe(true)

    // checkAuth fires loadAdminCapabilities; wait for the in-flight promise.
    await authStore.loadAdminCapabilities()

    expect(refreshSessionAccessToken).toHaveBeenCalledTimes(1)
    expect(capabilitiesHits).toBe(2)
    expect(authStore.adminCapabilitiesPayload?.panel_access).toBe(true)
    expect(authStore.adminCapabilitiesLoaded).toBe(true)
  })
})
