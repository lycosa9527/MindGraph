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

function fullDiagram(
  id: string,
  nodeCount: number,
  overrides: Record<string, unknown> = {}
): Record<string, unknown> {
  return {
    id,
    title: 'Map',
    diagram_type: 'mindmap',
    thumbnail: null,
    updated_at: '2026-01-01T00:00:00Z',
    is_pinned: false,
    language: 'zh',
    created_at: '2026-01-01T00:00:00Z',
    spec: {
      type: 'mindmap',
      nodes: Array.from({ length: nodeCount }, (_, i) => ({
        id: i === 0 ? 'topic' : `branch-${i}`,
        text: `n${i}`,
      })),
    },
    ...overrides,
  }
}

describe('savedDiagrams detail cache after update', () => {
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
    authFetchMock.mockReset()
    stubAuthUser()
  })

  it('refreshes detail cache on PUT so reopen does not hydrate stale spec', async () => {
    const diagramId = '65b9f2b3-597a-4c21-8bc4-a6b5e82ac5e5'
    let putBody: Record<string, unknown> | null = null
    authFetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const path = String(url)
      if (path === `/api/diagrams/${diagramId}` && (!init || !init.method || init.method === 'GET')) {
        return jsonResponse(fullDiagram(diagramId, 57))
      }
      if (path === `/api/diagrams/${diagramId}` && init?.method === 'PUT') {
        putBody = JSON.parse(String(init.body)) as Record<string, unknown>
        return jsonResponse(fullDiagram(diagramId, 13, { updated_at: '2026-01-01T00:01:00Z' }))
      }
      return jsonResponse({ detail: 'unexpected' }, 500)
    })

    const store = useSavedDiagramsStore()
    const first = await store.getDiagram(diagramId)
    expect(first.ok).toBe(true)
    if (!first.ok) return
    expect((first.diagram.spec.nodes as unknown[]).length).toBe(57)

    const updated = await store.updateDiagram(diagramId, {
      spec: fullDiagram(diagramId, 13).spec as Record<string, unknown>,
    })
    expect(updated).toBe(true)
    expect(putBody?.if_updated_at).toBeUndefined()
    expect(putBody?.spec).toBeTruthy()

    authFetchMock.mockClear()
    const second = await store.getDiagram(diagramId)
    expect(second.ok).toBe(true)
    if (!second.ok) return
    expect((second.diagram.spec.nodes as unknown[]).length).toBe(13)
    expect(authFetchMock).not.toHaveBeenCalled()
  })

  it('invalidates detail cache on 409 conflict', async () => {
    const diagramId = 'd-conflict'
    authFetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const path = String(url)
      if (path === `/api/diagrams/${diagramId}` && (!init || !init.method || init.method === 'GET')) {
        return jsonResponse(fullDiagram(diagramId, 3))
      }
      if (path === `/api/diagrams/${diagramId}` && init?.method === 'PUT') {
        return jsonResponse(
          { detail: 'Diagram was modified elsewhere; reload and retry.' },
          409
        )
      }
      return jsonResponse({ detail: 'unexpected' }, 500)
    })

    const store = useSavedDiagramsStore()
    expect((await store.getDiagram(diagramId)).ok).toBe(true)
    expect(store.getCachedDiagram(diagramId)).not.toBeNull()

    const ok = await store.updateDiagram(diagramId, { title: 'New' })
    expect(ok).toBe(false)
    expect(store.getCachedDiagram(diagramId)).toBeNull()
    expect(store.error).toContain('modified elsewhere')
  })

  it('drops detail cache when the diagram is deleted', async () => {
    const diagramId = 'd-delete'
    authFetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const path = String(url)
      if (path === `/api/diagrams/${diagramId}` && (!init || !init.method || init.method === 'GET')) {
        return jsonResponse(fullDiagram(diagramId, 3))
      }
      if (path === `/api/diagrams/${diagramId}` && init?.method === 'DELETE') {
        return jsonResponse({ ok: true })
      }
      return jsonResponse({ detail: 'unexpected' }, 500)
    })

    const store = useSavedDiagramsStore()
    store.diagrams = [
      {
        id: diagramId,
        title: 'Map',
        diagram_type: 'mindmap',
        thumbnail: null,
        updated_at: '2026-01-01T00:00:00Z',
        is_pinned: false,
      },
    ]
    store.total = 1

    expect((await store.getDiagram(diagramId)).ok).toBe(true)
    expect(await store.deleteDiagram(diagramId)).toBe(true)
    expect(store.getCachedDiagram(diagramId)).toBeNull()
  })

  it('force:true bypasses cache and always hits network', async () => {
    const diagramId = 'd-force'
    authFetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const path = String(url)
      if (path === `/api/diagrams/${diagramId}` && (!init || !init.method || init.method === 'GET')) {
        return jsonResponse(fullDiagram(diagramId, 5, { updated_at: '2026-01-01T00:00:00Z' }))
      }
      return jsonResponse({ detail: 'unexpected' }, 500)
    })

    const store = useSavedDiagramsStore()
    expect((await store.getDiagram(diagramId)).ok).toBe(true)
    authFetchMock.mockClear()

    authFetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const path = String(url)
      if (path === `/api/diagrams/${diagramId}` && (!init || !init.method || init.method === 'GET')) {
        return jsonResponse(fullDiagram(diagramId, 9, { updated_at: '2026-01-01T00:02:00Z' }))
      }
      return jsonResponse({ detail: 'unexpected' }, 500)
    })

    const forced = await store.getDiagram(diagramId, { force: true })
    expect(forced.ok).toBe(true)
    if (!forced.ok) return
    expect((forced.diagram.spec.nodes as unknown[]).length).toBe(9)
    expect(authFetchMock).toHaveBeenCalledTimes(1)
    expect(store.getCachedDiagram(diagramId)?.updated_at).toBe('2026-01-01T00:02:00Z')
  })

  it('force:true failure does not fall back to stale cache', async () => {
    const diagramId = 'd-force-fail'
    authFetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const path = String(url)
      if (path === `/api/diagrams/${diagramId}` && (!init || !init.method || init.method === 'GET')) {
        return jsonResponse(fullDiagram(diagramId, 4))
      }
      return jsonResponse({ detail: 'unexpected' }, 500)
    })

    const store = useSavedDiagramsStore()
    expect((await store.getDiagram(diagramId)).ok).toBe(true)
    expect(store.getCachedDiagram(diagramId)).not.toBeNull()

    authFetchMock.mockImplementation(async () => jsonResponse({ detail: 'gone' }, 500))
    const forced = await store.getDiagram(diagramId, { force: true })
    expect(forced.ok).toBe(false)
    if (forced.ok) return
    expect(forced.reason).toBe('network')
  })

  it('non-force GET with older updated_at does not clobber newer write-through', async () => {
    const diagramId = 'd-guard'
    let resolveSlowGet: ((response: Response) => void) | null = null

    authFetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const path = String(url)
      if (path === `/api/diagrams/${diagramId}` && (!init || !init.method || init.method === 'GET')) {
        return new Promise<Response>((resolve) => {
          resolveSlowGet = resolve
        })
      }
      if (path === `/api/diagrams/${diagramId}` && init?.method === 'PUT') {
        return jsonResponse(fullDiagram(diagramId, 13, { updated_at: '2026-01-01T00:05:00Z' }))
      }
      return jsonResponse({ detail: 'unexpected' }, 500)
    })

    const store = useSavedDiagramsStore()
    const slowGet = store.getDiagram(diagramId)

    // Wait until the in-flight GET is blocked on the mock.
    await vi.waitFor(() => {
      expect(resolveSlowGet).not.toBeNull()
    })

    const updated = await store.updateDiagram(diagramId, {
      spec: fullDiagram(diagramId, 13).spec as Record<string, unknown>,
    })
    expect(updated).toBe(true)
    expect(store.getCachedDiagram(diagramId)?.updated_at).toBe('2026-01-01T00:05:00Z')
    expect((store.getCachedDiagram(diagramId)?.spec.nodes as unknown[]).length).toBe(13)

    resolveSlowGet!(
      jsonResponse(fullDiagram(diagramId, 57, { updated_at: '2026-01-01T00:00:00Z' }))
    )
    const late = await slowGet
    expect(late.ok).toBe(true)

    // Guarded set keeps the newer PUT snapshot; late prefetch-like GET loses.
    const cached = store.getCachedDiagram(diagramId)
    expect(cached?.updated_at).toBe('2026-01-01T00:05:00Z')
    expect((cached?.spec.nodes as unknown[]).length).toBe(13)
  })

  it('force:true always replaces cache even with older updated_at', async () => {
    const diagramId = 'd-force-older'
    authFetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      const path = String(url)
      if (path === `/api/diagrams/${diagramId}` && init?.method === 'PUT') {
        return jsonResponse(fullDiagram(diagramId, 13, { updated_at: '2026-01-01T00:05:00Z' }))
      }
      if (path === `/api/diagrams/${diagramId}` && (!init || !init.method || init.method === 'GET')) {
        return jsonResponse(fullDiagram(diagramId, 2, { updated_at: '2026-01-01T00:00:00Z' }))
      }
      return jsonResponse({ detail: 'unexpected' }, 500)
    })

    const store = useSavedDiagramsStore()
    expect(
      await store.updateDiagram(diagramId, {
        spec: fullDiagram(diagramId, 13).spec as Record<string, unknown>,
      })
    ).toBe(true)
    expect(store.getCachedDiagram(diagramId)?.updated_at).toBe('2026-01-01T00:05:00Z')

    const forced = await store.getDiagram(diagramId, { force: true })
    expect(forced.ok).toBe(true)
    if (!forced.ok) return
    expect(forced.diagram.updated_at).toBe('2026-01-01T00:00:00Z')
    expect(store.getCachedDiagram(diagramId)?.updated_at).toBe('2026-01-01T00:00:00Z')
    expect((store.getCachedDiagram(diagramId)?.spec.nodes as unknown[]).length).toBe(2)
  })
})
