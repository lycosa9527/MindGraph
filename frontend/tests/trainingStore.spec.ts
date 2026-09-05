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

  it('applies a restarted session so teachers can be pulled again', () => {
    const store = useTrainingStore()
    store.applySnapshot(snapshot({ seq: 12 }))
    store.markApplied(12)
    store.setCommandEtag('"sess-1:12"')
    store.applySnapshot(snapshot({ state: 'ended', seq: 13 }))
    store.applySnapshot(
      snapshot({
        session_id: 'sess-2',
        seq: 1,
        diagram_type: 'circle_map',
      })
    )
    expect(store.snapshot.session_id).toBe('sess-2')
    expect(store.snapshot.seq).toBe(1)
    expect(store.lastAppliedSeq).toBe(0)
    expect(store.commandEtag).toBeNull()
  })

  it('keeps the hosted school when the picker changes', async () => {
    const store = useTrainingStore()
    store.applySnapshot(snapshot({ org_id: 10, instructor_id: 1 }))
    store.selectedOrgId = 10
    expect(await store.selectOrg(99)).toBe('locked')
    expect(store.selectedOrgId).toBe(10)
    expect(store.leadingOrgId).toBe(10)
    expect(store.snapshot.org_id).toBe(10)
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

  it('owns etag, org, and topics-drag through setters', () => {
    const store = useTrainingStore()
    store.setCommandEtag('"n-3"')
    store.setLeadingOrgId(10)
    store.setTopicsDragLive(true)
    expect(store.commandEtag).toBe('"n-3"')
    expect(store.leadingOrgId).toBe(10)
    expect(store.topicsDragLive).toBe(true)
    store.reset()
    expect(store.commandEtag).toBeNull()
    expect(store.leadingOrgId).toBeNull()
    expect(store.topicsDragLive).toBe(false)
  })
})
