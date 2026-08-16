import { describe, expect, it } from 'vitest'

import { lecturePlaybackIsIdle } from '@/composables/kitty/kittyAgentInbound'

describe('lecturePlaybackIsIdle', () => {
  it('waits until synthesis, decode, and queued PCM are all finished', () => {
    expect(
      lecturePlaybackIsIdle({
        synthesisDone: true,
        decodeInFlight: 0,
        scheduledCount: 0,
        queuedCount: 0,
      })
    ).toBe(true)
    expect(
      lecturePlaybackIsIdle({
        synthesisDone: true,
        decodeInFlight: 0,
        scheduledCount: 1,
        queuedCount: 0,
      })
    ).toBe(false)
    expect(
      lecturePlaybackIsIdle({
        synthesisDone: true,
        decodeInFlight: 1,
        scheduledCount: 0,
        queuedCount: 0,
      })
    ).toBe(false)
    expect(
      lecturePlaybackIsIdle({
        synthesisDone: false,
        decodeInFlight: 0,
        scheduledCount: 0,
        queuedCount: 0,
      })
    ).toBe(false)
  })
})
