import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import {
  beginQuietBranchComplete,
  cancelQuietBranchComplete,
  endQuietBranchComplete,
  resetQuietBranchCompleteBatchForTests,
} from '@/composables/kitty/kittyQuietBranchCompleteBatch'

vi.mock('@/i18n', () => ({
  i18n: {
    global: {
      t: (key: string) => key,
    },
  },
}))

describe('kittyQuietBranchCompleteBatch', () => {
  beforeEach(() => {
    resetQuietBranchCompleteBatchForTests()
    vi.useFakeTimers()
  })

  afterEach(() => {
    resetQuietBranchCompleteBatchForTests()
    vi.useRealTimers()
  })

  it('coalesces multiple successes into one branches-ready reply', () => {
    const spy = vi.fn()
    eventBus.on('kitty:diagram_action_completed', spy)

    beginQuietBranchComplete()
    beginQuietBranchComplete()
    beginQuietBranchComplete()
    endQuietBranchComplete(true)
    endQuietBranchComplete(true)
    endQuietBranchComplete(true)

    expect(spy).not.toHaveBeenCalled()
    vi.advanceTimersByTime(50)

    expect(spy).toHaveBeenCalledTimes(1)
    expect(spy.mock.calls[0]?.[0]).toMatchObject({
      action: 'auto_complete_branch',
      ok: true,
      userSummary: 'canvas.mindMapOneSentence.kittyBranchesCompleteDone',
    })

    eventBus.off('kitty:diagram_action_completed', spy)
  })

  it('uses singular copy for one success', () => {
    const spy = vi.fn()
    eventBus.on('kitty:diagram_action_completed', spy)

    beginQuietBranchComplete()
    endQuietBranchComplete(true)
    vi.advanceTimersByTime(50)

    expect(spy.mock.calls[0]?.[0]).toMatchObject({
      ok: true,
      userSummary: 'canvas.mindMapOneSentence.kittyBranchCompleteDone',
    })

    eventBus.off('kitty:diagram_action_completed', spy)
  })

  it('reports partial when some fail', () => {
    const spy = vi.fn()
    eventBus.on('kitty:diagram_action_completed', spy)

    beginQuietBranchComplete()
    beginQuietBranchComplete()
    endQuietBranchComplete(true)
    endQuietBranchComplete(false)
    vi.advanceTimersByTime(50)

    expect(spy.mock.calls[0]?.[0]).toMatchObject({
      ok: true,
      userSummary: 'canvas.mindMapOneSentence.kittyBranchesCompletePartial',
    })

    eventBus.off('kitty:diagram_action_completed', spy)
  })

  it('ignores cancelled jobs when flushing remaining results', () => {
    const spy = vi.fn()
    eventBus.on('kitty:diagram_action_completed', spy)

    beginQuietBranchComplete()
    beginQuietBranchComplete()
    endQuietBranchComplete(true)
    cancelQuietBranchComplete()
    vi.advanceTimersByTime(50)

    expect(spy).toHaveBeenCalledTimes(1)
    expect(spy.mock.calls[0]?.[0]).toMatchObject({
      ok: true,
      userSummary: 'canvas.mindMapOneSentence.kittyBranchCompleteDone',
    })

    eventBus.off('kitty:diagram_action_completed', spy)
  })
})
