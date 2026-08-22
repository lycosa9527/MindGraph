import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/utils/sessionRefresh', () => ({
  refreshSessionAccessToken: vi.fn(),
}))

import { useAuthStore } from '@/stores/auth'
import { useUIStore } from '@/stores/ui'

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
    getItem: (key) => map.get(key) ?? null,
    key: (index) => [...map.keys()][index] ?? null,
    removeItem: (key) => {
      map.delete(key)
    },
    setItem: (key, value) => {
      map.set(key, value)
    },
  }
}

describe('login restores persisted UI language', () => {
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

  it('applies zh from the login profile after the guest page followed English Chrome', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/auth/login')) {
        return jsonResponse({
          user: {
            id: 7,
            name: 'Ada',
            phone: '13800000000',
            role: 'teacher',
            ui_language: 'zh',
            prompt_language: 'zh',
            match_prompt_to_ui: true,
            allows_simplified_chinese: true,
          },
        })
      }
      if (url.includes('/api/auth/language-preferences')) {
        return jsonResponse({
          ui_language: 'en',
          prompt_language: 'en',
          match_prompt_to_ui: true,
        })
      }
      return jsonResponse({})
    })
    vi.stubGlobal('fetch', fetchMock)

    const uiStore = useUIStore()
    uiStore.syncGuestLocaleFromBrowser()
    expect(uiStore.language).toBe('en')

    const authStore = useAuthStore()
    const result = await authStore.login({
      phone: '13800000000',
      password: 'secret',
      captcha: 'x',
      captcha_id: 'y',
    })

    expect(result.success).toBe(true)
    expect(authStore.user?.uiLanguage).toBe('zh')
    expect(uiStore.language).toBe('zh')
    expect(
      fetchMock.mock.calls.some((call) => String(call[0]).includes('/api/auth/language-preferences'))
    ).toBe(false)
  })

  it('seeds the current UI language when the server has no saved ui_language', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/auth/login')) {
        return jsonResponse({
          user: {
            id: 8,
            name: 'Ada',
            phone: '13800000000',
            role: 'teacher',
            match_prompt_to_ui: true,
            allows_simplified_chinese: true,
          },
        })
      }
      if (url.includes('/api/auth/language-preferences')) {
        const body = JSON.parse(String(init?.body ?? '{}')) as { ui_language?: string }
        return jsonResponse({
          ui_language: body.ui_language ?? 'zh',
          prompt_language: 'zh',
          match_prompt_to_ui: true,
        })
      }
      return jsonResponse({})
    })
    vi.stubGlobal('fetch', fetchMock)

    const uiStore = useUIStore()
    uiStore.setLanguage('zh')
    uiStore.setUiLanguageExplicit(true)

    const authStore = useAuthStore()
    const result = await authStore.login({
      phone: '13800000000',
      password: 'secret',
      captcha: 'x',
      captcha_id: 'y',
    })

    expect(result.success).toBe(true)
    expect(uiStore.language).toBe('zh')
    await vi.waitFor(() => {
      expect(
        fetchMock.mock.calls.some((call) =>
          String(call[0]).includes('/api/auth/language-preferences')
        )
      ).toBe(true)
    })
    const prefCall = fetchMock.mock.calls.find((call) =>
      String(call[0]).includes('/api/auth/language-preferences')
    )
    const prefBody = JSON.parse(String(prefCall?.[1]?.body ?? '{}')) as {
      ui_language?: string
      ui_version?: string
    }
    expect(prefBody.ui_language).toBe('zh')
    expect(prefBody.ui_version).toBeUndefined()
  })

  it('always uses the current MindGraph gallery, including leftover chinese profiles', () => {
    const uiStore = useUIStore()
    uiStore.setUiVersion('chinese')
    expect(uiStore.uiVersion).toBe('international')
    uiStore.applyUiVersionFromServerProfile(null)
    expect(uiStore.uiVersion).toBe('international')
    uiStore.applyUiVersionFromServerProfile('chinese')
    expect(uiStore.uiVersion).toBe('international')
  })

  it('restores Simplified Chinese from a zh-CN profile tag without seeding English', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/auth/login')) {
        return jsonResponse({
          user: {
            id: 9,
            name: 'Ada',
            phone: '13800000000',
            role: 'teacher',
            ui_language: 'zh-CN',
            prompt_language: 'zh',
            match_prompt_to_ui: true,
            allows_simplified_chinese: true,
          },
        })
      }
      if (url.includes('/api/auth/language-preferences')) {
        return jsonResponse({
          ui_language: 'en',
          prompt_language: 'en',
          match_prompt_to_ui: true,
        })
      }
      return jsonResponse({})
    })
    vi.stubGlobal('fetch', fetchMock)

    const uiStore = useUIStore()
    uiStore.syncGuestLocaleFromBrowser()
    expect(uiStore.language).toBe('en')

    const authStore = useAuthStore()
    const result = await authStore.login({
      phone: '13800000000',
      password: 'secret',
      captcha: 'x',
      captcha_id: 'y',
    })

    expect(result.success).toBe(true)
    expect(authStore.user?.uiLanguage).toBe('zh')
    expect(uiStore.language).toBe('zh')
    expect(
      fetchMock.mock.calls.some((call) => String(call[0]).includes('/api/auth/language-preferences'))
    ).toBe(false)

    authStore.setUser({
      id: 9,
      name: 'Ada',
      phone: '13800000000',
      role: 'teacher',
      ui_language: 'zh',
      prompt_language: 'zh',
      match_prompt_to_ui: true,
      allows_simplified_chinese: true,
    })
    expect(uiStore.language).toBe('zh')
    expect(
      fetchMock.mock.calls.filter((call) =>
        String(call[0]).includes('/api/auth/language-preferences')
      )
    ).toHaveLength(0)
  })

  it('does not seed-overwrite an unrecognized saved ui_language', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/auth/login')) {
        return jsonResponse({
          user: {
            id: 10,
            name: 'Ada',
            phone: '13800000000',
            role: 'teacher',
            ui_language: 'zzz',
            match_prompt_to_ui: true,
            allows_simplified_chinese: true,
          },
        })
      }
      if (url.includes('/api/auth/language-preferences')) {
        return jsonResponse({
          ui_language: 'en',
          prompt_language: 'en',
          match_prompt_to_ui: true,
        })
      }
      return jsonResponse({})
    })
    vi.stubGlobal('fetch', fetchMock)

    const uiStore = useUIStore()
    uiStore.setLanguage('zh')
    uiStore.setUiLanguageExplicit(true)

    const authStore = useAuthStore()
    const result = await authStore.login({
      phone: '13800000000',
      password: 'secret',
      captcha: 'x',
      captcha_id: 'y',
    })

    expect(result.success).toBe(true)
    expect(uiStore.language).toBe('zh')
    await vi.waitFor(() => {
      expect(authStore.user?.id).toBe('10')
    })
    expect(
      fetchMock.mock.calls.some((call) => String(call[0]).includes('/api/auth/language-preferences'))
    ).toBe(false)
  })
})
