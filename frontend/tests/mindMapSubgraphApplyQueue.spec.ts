import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  enqueueSubgraphApply,
  resetSubgraphApplyQueueForTests,
  withSubgraphFetchSlot,
} from '@/composables/editor/mindMapSubgraphApplyQueue'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'

describe('mindMapSubgraphApplyQueue', () => {
  beforeEach(() => {
    resetSubgraphApplyQueueForTests()
  })

  it('serializes apply jobs', async () => {
    const order: number[] = []
    const slow = enqueueSubgraphApply(async () => {
      await new Promise((r) => setTimeout(r, 30))
      order.push(1)
      return 1
    })
    const fast = enqueueSubgraphApply(async () => {
      order.push(2)
      return 2
    })
    await Promise.all([slow, fast])
    expect(order).toEqual([1, 2])
  })

  it('allows parallel fetch slots up to the cap', async () => {
    let concurrent = 0
    let maxConcurrent = 0
    const jobs = Array.from({ length: 4 }, () =>
      withSubgraphFetchSlot(async () => {
        concurrent += 1
        maxConcurrent = Math.max(maxConcurrent, concurrent)
        await new Promise((r) => setTimeout(r, 20))
        concurrent -= 1
      })
    )
    await Promise.all(jobs)
    expect(maxConcurrent).toBe(4)
  })
})

describe('mindMapSubgraphPreview multi-flight', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('tracks multiple generating node ids without aborting peers', () => {
    const store = useMindMapSubgraphPreviewStore()
    const jobA = store.beginGeneration('branch-a')
    const jobB = store.beginGeneration('branch-b')
    expect(store.isGenerating).toBe(true)
    expect(store.isGeneratingFor('branch-a')).toBe(true)
    expect(store.isGeneratingFor('branch-b')).toBe(true)
    expect(jobA.signal.aborted).toBe(false)
    expect(jobB.signal.aborted).toBe(false)
    store.finishJob(jobA.jobKey)
    expect(store.isGeneratingFor('branch-a')).toBe(false)
    expect(store.isGeneratingFor('branch-b')).toBe(true)
    expect(jobB.signal.aborted).toBe(false)
  })

  it('finishes by jobKey after node id remap', () => {
    const store = useMindMapSubgraphPreviewStore()
    const job = store.beginGeneration('branch-r-1-0')
    store.remapGeneratingNodeIds((id) => (id === 'branch-r-1-0' ? 'branch-r-1-9' : id))
    expect(store.isGeneratingFor('branch-r-1-9')).toBe(true)
    expect(store.isGeneratingFor('branch-r-1-0')).toBe(false)
    store.finishJob(job.jobKey)
    expect(store.isGenerating).toBe(false)
    expect(job.signal.aborted).toBe(false)
  })

  it('remaps generating ids after reload', () => {
    const store = useMindMapSubgraphPreviewStore()
    store.beginGeneration('branch-r-1-0')
    store.beginGeneration('branch-r-1-1')
    store.remapGeneratingNodeIds((id) => (id === 'branch-r-1-0' ? 'branch-r-1-9' : id))
    expect(store.isGeneratingFor('branch-r-1-9')).toBe(true)
    expect(store.isGeneratingFor('branch-r-1-1')).toBe(true)
    expect(store.isGeneratingFor('branch-r-1-0')).toBe(false)
  })
})
