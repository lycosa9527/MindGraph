import { createApp, defineComponent } from 'vue'

import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useTrainingFollow } from '@/composables/training/useTrainingFollow'
import { useTrainingStore } from '@/stores/training'
import type { TrainingSnapshot } from '@/types/training'
import { MINDGRAPH_HEADLESS_EXPORT_KEY } from '@/utils/headlessExportSession'

const fetchCommand = vi.hoisted(() => vi.fn())
const postActivity = vi.hoisted(() => vi.fn().mockResolvedValue(undefined))
const navigateMock = vi.hoisted(() => vi.fn().mockResolvedValue(true))
const routePath = vi.hoisted(() => ({ value: '/mindmate' }))
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
  postTrainingActivity: (...args: unknown[]) => postActivity(...args),
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
    beforeEach: () => () => undefined,
    currentRoute: { value: { path: '/mindmate', query: {} } },
  }),
  useRoute: () => ({ path: routePath.value }),
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

async function flushTurns(times = 8): Promise<void> {
  for (let index = 0; index < times; index += 1) {
    await Promise.resolve()
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
    postActivity.mockClear()
    navigateMock.mockClear()
    routePath.value = '/mindmate'
    applyUiMock.mockClear()
    FakeEventSource.latest = null
    sessionStorage.clear()
    authState.isPlatformLevel = false
    authState.isTeacher = true
    authState.user = { id: '3', schoolId: '12' }
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
    authState.isPlatformLevel = false
    authState.user = { id: '3', schoolId: '12' }
  })

  it('applies a live seq and ignores a later stale snapshot', async () => {
    const { app, host, store } = mountFollow()
    await flushTurns()
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
    await flushTurns()
    expect(store.snapshot.seq).toBe(5)
    expect(navigateMock).not.toHaveBeenCalled()
    app.unmount()
    host.remove()
  })

  it('pulls teachers into a restarted session at seq 1', async () => {
    const { app, host, store } = mountFollow()
    await flushTurns()
    store.applySnapshot(snapshot({ state: 'ended', seq: 13 }))
    navigateMock.mockClear()
    fetchCommand.mockResolvedValueOnce({
      snapshot: snapshot({
        session_id: 'sess-2',
        seq: 1,
        diagram_type: 'circle_map',
      }),
      etag: '"sess-2:1"',
      notModified: false,
    })
    FakeEventSource.latest?.emit('seq')
    await flushTurns()
    expect(store.snapshot.session_id).toBe('sess-2')
    expect(store.snapshot.seq).toBe(1)
    expect(navigateMock).toHaveBeenCalled()
    app.unmount()
    host.remove()
  })

  it('falls back to polling after EventSource error', async () => {
    vi.useFakeTimers()
    const { app, host } = mountFollow()
    await flushTurns()
    fetchCommand.mockClear()
    FakeEventSource.latest?.onerror?.()
    await vi.advanceTimersByTimeAsync(2000)
    expect(fetchCommand).toHaveBeenCalled()
    app.unmount()
    host.remove()
  })

  it('refetches when the tab becomes visible', async () => {
    const { app, host } = mountFollow()
    await flushTurns()
    fetchCommand.mockClear()
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    })
    document.dispatchEvent(new Event('visibilitychange'))
    await flushTurns()
    expect(fetchCommand).toHaveBeenCalled()
    app.unmount()
    host.remove()
  })

  it('force-navs teachers when the instructor switches from free to pull', async () => {
    const { app, host, store } = mountFollow()
    await flushTurns()
    navigateMock.mockClear()
    store.markApplied(5)
    fetchCommand.mockResolvedValueOnce({
      snapshot: snapshot({
        seq: 6,
        pull_users: false,
        course_id: 'c1',
        step: { position: 0, type: 'page', page_key: 'canvas' },
      }),
      etag: '"6"',
      notModified: false,
    })
    FakeEventSource.latest?.emit('seq')
    await flushTurns()
    expect(navigateMock).not.toHaveBeenCalled()
    expect(store.lastAppliedSeq).toBe(6)
    fetchCommand.mockResolvedValueOnce({
      snapshot: snapshot({
        seq: 7,
        pull_users: true,
        course_id: 'c1',
        step: { position: 0, type: 'page', page_key: 'canvas' },
      }),
      etag: '"7"',
      notModified: false,
    })
    FakeEventSource.latest?.emit('seq')
    await flushTurns()
    expect(navigateMock).toHaveBeenCalled()
    expect(store.lastAppliedSeq).toBe(7)
    app.unmount()
    host.remove()
  })

  it('does not force-nav anyone off the phone remote', async () => {
    routePath.value = '/m/training'
    const { app, host, store } = mountFollow()
    await flushTurns()
    navigateMock.mockClear()
    store.markApplied(5)
    fetchCommand.mockResolvedValueOnce({
      snapshot: snapshot({
        seq: 8,
        pull_users: true,
        course_id: 'c1',
        step: { position: 0, type: 'page', page_key: 'canvas' },
      }),
      etag: '"8"',
      notModified: false,
    })
    FakeEventSource.latest?.emit('seq')
    await flushTurns()
    expect(navigateMock).not.toHaveBeenCalled()
    expect(store.lastAppliedSeq).toBe(8)
    app.unmount()
    host.remove()
  })

  it('does not force-nav the hosting instructor off mobile home', async () => {
    routePath.value = '/m'
    authState.user = { id: '1', schoolId: '12' }
    const { app, host, store } = mountFollow()
    await flushTurns()
    navigateMock.mockClear()
    store.markApplied(5)
    fetchCommand.mockResolvedValueOnce({
      snapshot: snapshot({
        seq: 9,
        pull_users: true,
        course_id: 'c1',
        instructor_id: 1,
        step: { position: 0, type: 'page', page_key: 'canvas' },
      }),
      etag: '"9"',
      notModified: false,
    })
    FakeEventSource.latest?.emit('seq')
    await flushTurns()
    expect(navigateMock).not.toHaveBeenCalled()
    expect(store.lastAppliedSeq).toBe(9)
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

  it('does not open EventSource for a platform lead until the school is known', async () => {
    authState.isPlatformLevel = true
    authState.user = { id: '3', schoolId: '' }
    const { app, host } = mountFollow()
    await flushTurns()
    expect(FakeEventSource.latest).toBeNull()
    expect(fetchCommand).not.toHaveBeenCalled()
    app.unmount()
    host.remove()
  })

  it('does not post teacher activity from the phone remote', async () => {
    routePath.value = '/m/training'
    const { app, host } = mountFollow()
    await flushTurns()
    expect(postActivity).not.toHaveBeenCalled()
    app.unmount()
    host.remove()
  })
})
