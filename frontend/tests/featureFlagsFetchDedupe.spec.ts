import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const apiRequestMock = vi.hoisted(() => vi.fn())

vi.mock('@/utils/apiClient', () => ({
  apiRequest: apiRequestMock,
}))

vi.mock('@/stores/ui', () => ({
  MINDMAP_CANVAS_MODE_KEY: 'mindmap_canvas_mode',
  useUIStore: () => ({
    mindMapCanvasMode: 'v2',
    setMindMapCanvasMode: vi.fn(),
  }),
}))

import { useFeatureFlagsStore } from '@/stores/featureFlags'

function flagsResponse(overrides: Record<string, unknown> = {}): Response {
  return new Response(
    JSON.stringify({
      external_base_url: '',
      feature_rag_chunk_test: false,
      feature_course: false,
      feature_mate_learning: false,
      feature_template: false,
      feature_community: false,
      feature_showcase: true,
      feature_zhihui: false,
      feature_askonce: false,
      feature_debateverse: false,
      feature_knowledge_space: false,
      feature_mindmap_v2_canvas: true,
      feature_mind_classroom_slide_deck: false,
      feature_library: true,
      feature_gewe: false,
      feature_smart_response: false,
      feature_teacher_usage: false,
      feature_workshop_chat: false,
      feature_mindmate_collab: false,
      feature_markets: false,
      feature_mindbot: false,
      feature_mindmate_export: false,
      feature_kitty_agent: false,
      feature_auth_pixel_battle: false,
      feature_test_server_banner: false,
      feature_oauth_login: false,
      feature_thinking_coins: false,
      workshop_chat_preview_org_ids: [],
      feature_org_access: {},
      ...overrides,
    }),
    { status: 200, headers: { 'Content-Type': 'application/json' } }
  )
}

describe('featureFlags fetchFlags dedupe', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    apiRequestMock.mockReset()
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })
  })

  it('coalesces concurrent fetchFlags into one network request', async () => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    apiRequestMock.mockImplementation(async () => {
      await gate
      return flagsResponse()
    })

    const store = useFeatureFlagsStore()
    const p1 = store.fetchFlags()
    const p2 = store.fetchFlags()
    const p3 = store.fetchFlags()

    expect(apiRequestMock).toHaveBeenCalledTimes(1)
    release()
    const [a, b, c] = await Promise.all([p1, p2, p3])
    expect(apiRequestMock).toHaveBeenCalledTimes(1)
    expect(a.feature_showcase).toBe(true)
    expect(b.feature_showcase).toBe(true)
    expect(c.feature_showcase).toBe(true)
    expect(b).toEqual(a)
    expect(c).toEqual(a)
  })

  it('returns TTL cache without a second network request', async () => {
    apiRequestMock.mockImplementation(async () => flagsResponse())
    const store = useFeatureFlagsStore()
    await store.fetchFlags()
    await store.fetchFlags()
    expect(apiRequestMock).toHaveBeenCalledTimes(1)
  })

  it('refetches after markStale', async () => {
    apiRequestMock.mockImplementation(async () => flagsResponse())
    const store = useFeatureFlagsStore()
    await store.fetchFlags()
    store.markStale()
    await store.fetchFlags()
    expect(apiRequestMock).toHaveBeenCalledTimes(2)
  })

  it('refetches when markStale runs during an in-flight fetch', async () => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    let calls = 0
    apiRequestMock.mockImplementation(async () => {
      calls += 1
      if (calls === 1) {
        await gate
        return flagsResponse({ feature_showcase: false })
      }
      return flagsResponse({ feature_showcase: true })
    })

    const store = useFeatureFlagsStore()
    const pending = store.fetchFlags()
    store.markStale()
    release()
    // Starter detects markStale invalidation and performs one follow-up fetch.
    const result = await pending
    expect(result.feature_showcase).toBe(true)
    expect(store.flags?.feature_showcase).toBe(true)
    expect(apiRequestMock).toHaveBeenCalledTimes(2)
  })
})
