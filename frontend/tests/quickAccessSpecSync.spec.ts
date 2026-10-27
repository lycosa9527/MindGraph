import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  loadQuickAccessSpecs,
  rememberQuickAccessSpec,
  resolveQuickAccessSpec,
} from '@/composables/sidebar/quickAccessSpecSync'
import { useAuthStore } from '@/stores/auth'

const authFetchMock = vi.hoisted(() => vi.fn())

vi.mock('@/utils/api', () => ({
  authFetch: authFetchMock,
}))

const PROMPT_KEY = 'landing.international.example1' as const

function stubAuthUser(): void {
  const authStore = useAuthStore()
  authStore.user = {
    id: '1',
    username: 'tester',
    phone: '100',
    role: 'personal_trial',
    avatar: '🙂',
  }
}

describe('quick access spec sync', () => {
  beforeEach(async () => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
    authFetchMock.mockReset()
    const authStore = useAuthStore()
    authStore.user = null
    await loadQuickAccessSpecs()
  })

  it.each([
    ['chrome', new TypeError('Failed to fetch')],
    ['safari', new TypeError('Load failed')],
    ['firefox', new TypeError('NetworkError when attempting to fetch resource.')],
    ['abort', new DOMException('The operation was aborted.', 'AbortError')],
  ])('resolves when the spec hydrate fails in %s', async (_browser, error) => {
    stubAuthUser()
    authFetchMock.mockRejectedValue(error)

    await expect(loadQuickAccessSpecs()).resolves.toBeUndefined()
    expect(resolveQuickAccessSpec(PROMPT_KEY, 'preset', 'preset')).toBeNull()
  })

  it('still reports a stale chunk failure from the spec hydrate', async () => {
    stubAuthUser()
    authFetchMock.mockRejectedValue(
      new TypeError('Failed to fetch dynamically imported module: https://mg.example/a.js')
    )

    await expect(loadQuickAccessSpecs()).rejects.toThrow(/dynamically imported module/)
  })

  it('reports a non-transport failure from the spec hydrate', async () => {
    stubAuthUser()
    authFetchMock.mockRejectedValue(new Error('session refresh blew up'))

    await expect(loadQuickAccessSpecs()).rejects.toThrow('session refresh blew up')
  })

  it('keeps a remembered spec when the save request fails', async () => {
    stubAuthUser()
    authFetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const saved = {
      text: 'custom topic',
      diagramType: 'mindmap' as const,
      spec: { topic: 'custom topic' },
    }

    await expect(rememberQuickAccessSpec(PROMPT_KEY, saved)).resolves.toBeUndefined()
    expect(resolveQuickAccessSpec(PROMPT_KEY, 'custom topic', 'preset')).toEqual(saved)
  })

  it('loads saved specs when the request succeeds', async () => {
    stubAuthUser()
    authFetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          defaults: {},
          saved: {
            [PROMPT_KEY]: {
              text: 'custom topic',
              diagramType: 'mindmap',
              spec: { topic: 'custom topic' },
            },
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    )

    await loadQuickAccessSpecs()

    expect(resolveQuickAccessSpec(PROMPT_KEY, 'custom topic', 'preset')).toEqual({
      text: 'custom topic',
      diagramType: 'mindmap',
      spec: { topic: 'custom topic' },
    })
  })
})
