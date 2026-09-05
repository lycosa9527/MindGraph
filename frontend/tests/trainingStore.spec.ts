import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it } from 'vitest'

import { useTrainingStore } from '@/stores/training'
import type { TrainingSnapshot } from '@/types/training'

function snapshot(overrides: Partial<TrainingSnapshot> = {}): TrainingSnapshot {
  return {
    state: 'live',
    session_id: 'sess-1',
    org_id: 10,
    seq: 4,
    diagram_type: 'double_bubble_map',
    topic_options: [],
    instructor_id: 1,
    instructor_name: 'Ada',
    ...overrides,
  }
}

describe('training store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('applies a newer snapshot and ignores a stale seq', () => {
    const store = useTrainingStore()
    store.applySnapshot(snapshot({ seq: 4 }))
    store.applySnapshot(snapshot({ seq: 6, diagram_type: 'tree_map' }))
    expect(store.snapshot.seq).toBe(6)
    expect(store.snapshot.diagram_type).toBe('tree_map')
    store.applySnapshot(snapshot({ seq: 5, diagram_type: 'circle_map' }))
    expect(store.snapshot.seq).toBe(6)
    expect(store.snapshot.diagram_type).toBe('tree_map')
  })

  it('tracks last applied seq monotonically', () => {
    const store = useTrainingStore()
    store.markApplied(3)
    store.markApplied(2)
    store.markApplied(8)
    expect(store.lastAppliedSeq).toBe(8)
  })

  it('clears the UI focus ring on reset', () => {
    const store = useTrainingStore()
    store.setUiFocus('diagram-mindmap')
    expect(store.uiFocusKey).toBe('diagram-mindmap')
    store.reset()
    expect(store.uiFocusKey).toBeNull()
  })
})
