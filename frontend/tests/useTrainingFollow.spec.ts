import { createApp, defineComponent } from 'vue'

import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useTrainingFollow } from '@/composables/training/useTrainingFollow'
import { useTrainingStore } from '@/stores/training'
import type { TrainingSnapshot } from '@/types/training'
import { MINDGRAPH_HEADLESS_EXPORT_KEY } from '@/utils/headlessExportSession'

const fetchCommand = vi.hoisted(() => vi.fn())
const navigateMock = vi.hoisted(() => vi.fn().mockResolvedValue(true))
const applyUiMock = vi.hoisted(() => vi.fn().mockResolvedValue(undefined))
const authState = vi.hoisted(() => ({
  isAuthenticated: true,
  isAuthSessionVerified: true,
  isC2CConsumer: false,
  isTeacher: true,
  isPlatformLevel: false,
  user: { id: '3', schoolId: '12' },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

vi.mock('@/stores/featureFlags', () => ({
  useFeatureFlagsStore: () => ({
    flags: { feature_training: true },
    getFeatureTraining: () => true,
  }),
}))

vi.mock('@/utils/trainingApi', () => ({
  fetchTrainingCommand: (...args: unknown[]) => fetchCommand(...args),
  postTrainingActivity: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/composables/training/applyTrainingUiTarget', () => ({
  applyTrainingUiTarget: (...args: unknown[]) => applyUiMock(...args),
}))

vi.mock('@/composables/training/applyTrainingSnapshot', async () => {
  const actual = await vi.importActual<
    typeof import('@/composables/training/applyTrainingSnapshot')
  >('@/composables/training/applyTrainingSnapshot')
  return {
    ...actual,
    applyTrainingNavigate: navigateMock,
  }
})

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
    currentRoute: { value: { path: '/mindmate', query: {} } },
  }),
  useRoute: () => ({ path: '/mindmate' }),
}))

class FakeEventSource {
  static latest: FakeEventSource | null = null
  url: string
  listeners: Record<string, Array<() => void>> = {}
  onerror: (() => void) | null = null
  closed = false

  constructor(url: string) {
    this.url = url
    FakeEventSource.latest = this
  }

  addEventListener(type: string, handler: () => void): void {
    if (!this.listeners[type]) this.listeners[type] = []
    this.listeners[type].push(handler)
  }

  close(): void {
    this.closed = true
  }

  emit(type: string): void {
    for (const handler of this.listeners[type] || []) handler()
  }
}

function snapshot(overrides: Partial<TrainingSnapshot> = {}): TrainingSnapshot {
  return {
    state: 'live',
    session_id: 'sess-1',
    org_id: 12,
    seq: 5,
    diagram_type: 'double_bubble_map',
    topic_options: [],
    instructor_id: 1,
    instructor_name: 'Ada',
    ...overrides,
  }
}

function mountFollow() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const app = createApp(
    defineComponent({
      setup() {
        useTrainingFollow()
        return () => null
      },
    })
  )
  app.use(pinia)
  const host = document.createElement('div')
  document.body.appendChild(host)
  app.mount(host)
  return { app, host, store: useTrainingStore() }
}

describe('useTrainingFollow', () => {
  beforeEach(() => {
    fetchCommand.mockReset()
    navigateMock.mockClear()
    applyUiMock.mockClear()
    FakeEventSource.latest = null
    sessionStorage.clear()
    vi.stubGlobal('EventSource', FakeEventSource)
    fetchCommand.mockResolvedValue({
      snapshot: snapshot(),
      etag: '"5"',
      notModified: false,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    sessionStorage.clear()
  })

  it('applies a live seq and ignores a later stale snapshot', async () => {
    const { app, host, store } = mountFollow()
    await Promise.resolve()
    await Promise.resolve()
    expect(navigateMock).toHaveBeenCalled()
    expect(applyUiMock).toHaveBeenCalled()
    store.markApplied(5)
    navigateMock.mockClear()
    fetchCommand.mockResolvedValueOnce({
      snapshot: snapshot({ seq: 3, diagram_type: 'circle_map' }),
      etag: '"3"',
      notModified: false,
    })
    FakeEventSource.latest?.emit('seq')
    await Promise.resolve()
    expect(store.snapshot.seq).toBe(5)
    expect(navigateMock).not.toHaveBeenCalled()
    app.unmount()
    host.remove()
  })

  it('falls back to polling after EventSource error', async () => {
    vi.useFakeTimers()
    const { app, host } = mountFollow()
    await Promise.resolve()
    fetchCommand.mockClear()
    FakeEventSource.latest?.onerror?.()
    await vi.advanceTimersByTimeAsync(2000)
    expect(fetchCommand).toHaveBeenCalled()
    app.unmount()
    host.remove()
  })

  it('refetches when the tab becomes visible', async () => {
    const { app, host } = mountFollow()
    await Promise.resolve()
    fetchCommand.mockClear()
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    })
    document.dispatchEvent(new Event('visibilitychange'))
    await Promise.resolve()
    expect(fetchCommand).toHaveBeenCalled()
    app.unmount()
    host.remove()
  })

  it('does not open EventSource during headless export', async () => {
    sessionStorage.setItem(MINDGRAPH_HEADLESS_EXPORT_KEY, '1')
    const { app, host } = mountFollow()
    await Promise.resolve()
    expect(FakeEventSource.latest).toBeNull()
    expect(fetchCommand).not.toHaveBeenCalled()
    app.unmount()
    host.remove()
  })
})
