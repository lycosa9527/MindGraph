import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const authFetchMock = vi.hoisted(() => vi.fn())

vi.mock('@/utils/api', () => ({
  authFetch: authFetchMock,
}))

vi.mock('@/composables/core/notifications', () => ({
  notify: { warning: vi.fn(), error: vi.fn(), success: vi.fn(), info: vi.fn() },
}))

import { useAuthStore } from '@/stores/auth'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

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

function mockListResponses(): void {
  authFetchMock.mockImplementation(async (url: string) => {
    if (String(url).includes('/api/diagram-folders')) {
      return jsonResponse({ folders: [] })
    }
    if (String(url).includes('/api/diagrams')) {
      return jsonResponse({
        diagrams: [{ id: 'd1', title: 'One', diagram_type: 'mindmap' }],
        total: 1,
        page: 1,
        page_size: 50,
        has_more: false,
        max_diagrams: 10,
      })
    }
    return jsonResponse({})
  })
}

function diagramsListCallCount(): number {
  return authFetchMock.mock.calls.filter((call) =>
    String(call[0]).includes('/api/diagrams?')
  ).length
}

describe('savedDiagrams fetchDiagrams dedupe', () => {
  beforeEach(() => {
    vi.useRealTimers()
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
    authFetchMock.mockReset()
    stubAuthUser()
    mockListResponses()
  })

  it('coalesces concurrent fetchDiagrams into one list+folders pair', async () => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    authFetchMock.mockImplementation(async (url: string) => {
      await gate
      if (String(url).includes('/api/diagram-folders')) {
        return jsonResponse({ folders: [] })
      }
      return jsonResponse({
        diagrams: [],
        total: 0,
        page: 1,
        page_size: 50,
        has_more: false,
        max_diagrams: 10,
      })
    })

    const store = useSavedDiagramsStore()
    const p1 = store.fetchDiagrams()
    const p2 = store.fetchDiagrams()
    const p3 = store.fetchDiagrams()
    expect(diagramsListCallCount()).toBe(1)
    release()
    await Promise.all([p1, p2, p3])
    expect(diagramsListCallCount()).toBe(1)
  })

  it('skips network within TTL unless force', async () => {
    const store = useSavedDiagramsStore()
    await store.fetchDiagrams()
    expect(diagramsListCallCount()).toBe(1)
    await store.fetchDiagrams()
    expect(diagramsListCallCount()).toBe(1)
    await store.fetchDiagrams(1, 50, { force: true })
    expect(diagramsListCallCount()).toBe(2)
  })

  it('clears TTL on reset so the next fetch hits the network', async () => {
    const store = useSavedDiagramsStore()
    await store.fetchDiagrams()
    store.reset()
    await store.fetchDiagrams()
    expect(diagramsListCallCount()).toBe(2)
  })

  it('invalidates TTL when the authenticated user changes', async () => {
    const store = useSavedDiagramsStore()
    await store.fetchDiagrams()
    expect(diagramsListCallCount()).toBe(1)
    expect(store.diagrams).toHaveLength(1)

    const authStore = useAuthStore()
    authStore.user = {
      id: '2',
      username: 'other',
      phone: '200',
      role: 'personal_trial',
      avatar: '🙂',
    }

    await store.fetchDiagrams()
    expect(diagramsListCallCount()).toBe(2)
  })

  it('force retries after a failed shared in-flight fetch', async () => {
    let attempt = 0
    authFetchMock.mockImplementation(async (url: string) => {
      if (String(url).includes('/api/diagram-folders')) {
        return jsonResponse({ folders: [] })
      }
      attempt += 1
      if (attempt === 1) {
        return jsonResponse({ detail: 'boom' }, 500)
      }
      return jsonResponse({
        diagrams: [{ id: 'd2', title: 'Two', diagram_type: 'mindmap' }],
        total: 1,
        page: 1,
        page_size: 50,
        has_more: false,
        max_diagrams: 10,
      })
    })

    const store = useSavedDiagramsStore()
    const p1 = store.fetchDiagrams()
    const p2 = store.fetchDiagrams(1, 50, { force: true })
    const [r1, r2] = await Promise.all([p1, p2])
    expect(r1).toBe(false)
    expect(r2).toBe(true)
    expect(diagramsListCallCount()).toBe(2)
    expect(store.diagrams[0]?.id).toBe('d2')
  })
})
