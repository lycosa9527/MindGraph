import { createApp, defineComponent } from 'vue'

import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useTrainingHeartbeat } from '@/composables/training/useTrainingHeartbeat'
import { useTrainingStore } from '@/stores/training'
import type { TrainingSnapshot } from '@/types/training'
import { emptyTrainingSnapshot } from '@/utils/trainingClient'

const postHeartbeat = vi.hoisted(() => vi.fn())

vi.mock('@/utils/trainingApi', () => ({
  postTrainingHeartbeat: (...args: unknown[]) => postHeartbeat(...args),
}))

function snapshot(overrides: Partial<TrainingSnapshot> = {}): TrainingSnapshot {
  return {
    state: 'live',
    session_id: 'c54f550e-3fb6-465c-ae88-568e25deff1f',
    org_id: 10,
    seq: 4,
    diagram_type: 'double_bubble_map',
    topic_options: [],
    instructor_id: 3,
    instructor_name: 'Ada',
    ...overrides,
  }
}

async function flushTurns(times = 8): Promise<void> {
  for (let index = 0; index < times; index += 1) {
    await Promise.resolve()
  }
}

function mountHeartbeat(enabled = () => true) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useTrainingStore()
  const app = createApp(
    defineComponent({
      setup() {
        useTrainingHeartbeat(enabled)
        return () => null
      },
    })
  )
  app.use(pinia)
  const host = document.createElement('div')
  document.body.appendChild(host)
  app.mount(host)
  return { app, host, store }
}

describe('useTrainingHeartbeat', () => {
  beforeEach(() => {
    postHeartbeat.mockReset()
    postHeartbeat.mockResolvedValue(snapshot())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('applies a gone snapshot and stops without rejecting', async () => {
    vi.useFakeTimers()
    postHeartbeat.mockResolvedValue(emptyTrainingSnapshot())
    const { app, host, store } = mountHeartbeat()
    store.applySnapshot(snapshot())
    await flushTurns()
    expect(store.snapshot.state).toBe('none')
    expect(store.snapshot.session_id).toBeNull()
    expect(store.isActive).toBe(false)
    postHeartbeat.mockClear()
    await vi.advanceTimersByTimeAsync(15000)
    expect(postHeartbeat).not.toHaveBeenCalled()
    app.unmount()
    host.remove()
  })

  it('applies a live heartbeat snapshot', async () => {
    postHeartbeat.mockResolvedValue(snapshot({ seq: 4, diagram_type: 'tree_map' }))
    const { app, host, store } = mountHeartbeat()
    store.applySnapshot(snapshot({ seq: 4 }))
    await flushTurns()
    expect(store.snapshot.diagram_type).toBe('tree_map')
    app.unmount()
    host.remove()
  })

  it('swallows a transient heartbeat failure', async () => {
    postHeartbeat.mockRejectedValue(new Error('network'))
    const { app, host, store } = mountHeartbeat()
    store.applySnapshot(snapshot())
    await flushTurns()
    expect(store.snapshot.session_id).toBe('c54f550e-3fb6-465c-ae88-568e25deff1f')
    expect(store.isActive).toBe(true)
    app.unmount()
    host.remove()
  })
})
