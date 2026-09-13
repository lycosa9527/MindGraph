import { describe, expect, it } from 'vitest'

import { waitForMindMapSlidePlayReady } from '@/composables/mindMap/waitForMindMapSlidePlayReady'

describe('waitForMindMapSlidePlayReady', () => {
  it('resolves after two frames when the map is already measured', async () => {
    await waitForMindMapSlidePlayReady(() => false)
  })

  it('keeps waiting while measure-batch is active', async () => {
    let bulk = true
    const done = waitForMindMapSlidePlayReady(() => bulk, 4000)
    window.setTimeout(() => {
      bulk = false
    }, 20)
    await done
    expect(bulk).toBe(false)
  })
})
