import { describe, expect, it, vi } from 'vitest'

import { createSlideRemoteDesktopPlay } from '@/composables/mindMap/createSlideRemoteDesktopPlay'

describe('createSlideRemoteDesktopPlay', () => {
  function makePlay(overrides: Partial<Parameters<typeof createSlideRemoteDesktopPlay>[0]> = {}) {
    return createSlideRemoteDesktopPlay({
      isRailOpen: () => false,
      openRail: vi.fn(),
      shouldUseSlidesTool: () => true,
      setSlidesTool: vi.fn(),
      ...overrides,
    })
  }

  it('opens the rail and waits for consumePending before starting slides', () => {
    const openRail = vi.fn()
    const setSlidesTool = vi.fn()
    const play = makePlay({ openRail, setSlidesTool })

    play.requestPlay()

    expect(openRail).toHaveBeenCalledOnce()
    expect(setSlidesTool).not.toHaveBeenCalled()
    expect(play.consumePending()).toBe(true)
    expect(setSlidesTool).toHaveBeenCalledOnce()
    expect(play.consumePending()).toBe(false)
  })

  it('starts slides immediately when the rail is already open', () => {
    const openRail = vi.fn()
    const setSlidesTool = vi.fn()
    const play = makePlay({
      isRailOpen: () => true,
      openRail,
      setSlidesTool,
    })

    play.requestPlay()

    expect(openRail).not.toHaveBeenCalled()
    expect(setSlidesTool).toHaveBeenCalledOnce()
  })

  it('does not start slides twice while a rail-open settle is in flight', () => {
    let railOpen = false
    const setSlidesTool = vi.fn()
    const play = makePlay({
      isRailOpen: () => railOpen,
      openRail: () => {
        railOpen = true
      },
      setSlidesTool,
    })

    play.requestPlay()
    play.requestPlay()

    expect(setSlidesTool).not.toHaveBeenCalled()
    expect(play.consumePending()).toBe(true)
    expect(setSlidesTool).toHaveBeenCalledOnce()
  })

  it('does not claim the enter-fit when slides chrome is unavailable', () => {
    const setSlidesTool = vi.fn()
    const play = makePlay({
      shouldUseSlidesTool: () => false,
      setSlidesTool,
    })

    play.requestPlay()

    expect(play.consumePending()).toBe(false)
    expect(setSlidesTool).not.toHaveBeenCalled()
  })

  it('clears a pending start when presentation closes', () => {
    const setSlidesTool = vi.fn()
    const play = makePlay({ setSlidesTool })

    play.requestPlay()
    play.clearPending()

    expect(play.consumePending()).toBe(false)
    expect(setSlidesTool).not.toHaveBeenCalled()
  })
})
