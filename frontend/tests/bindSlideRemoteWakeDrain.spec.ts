import { afterEach, describe, expect, it, vi } from 'vitest'

import { bindSlideRemoteWakeDrain } from '@/composables/mindMap/bindSlideRemoteWakeDrain'

describe('bindSlideRemoteWakeDrain', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('drains once on start and does not start an interval poll', () => {
    const drain = vi.fn().mockResolvedValue(undefined)
    const setIntervalSpy = vi.spyOn(window, 'setInterval')
    const binding = bindSlideRemoteWakeDrain({
      drain,
      shouldRun: () => true,
    })
    binding.start()
    expect(drain).toHaveBeenCalledOnce()
    expect(setIntervalSpy).not.toHaveBeenCalled()
    binding.stop()
  })

  it('does not start when shouldRun is false', () => {
    const drain = vi.fn().mockResolvedValue(undefined)
    const binding = bindSlideRemoteWakeDrain({
      drain,
      shouldRun: () => false,
    })
    binding.start()
    expect(drain).not.toHaveBeenCalled()
  })
})
