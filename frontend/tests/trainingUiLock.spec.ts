import { afterEach, describe, expect, it } from 'vitest'

import {
  applyTrainingUiLock,
  armTrainingUiLock,
  captureOpenTrainingUiLock,
  pushTrainingLockScope,
  registerTrainingUiLock,
  releaseTrainingUiLock,
  takeArmedTrainingUiLock,
} from '@/composables/training/trainingUiLock'

describe('trainingUiLock', () => {
  const stops: Array<() => void> = []

  afterEach(() => {
    for (const stop of stops) stop()
    stops.length = 0
    releaseTrainingUiLock()
    takeArmedTrainingUiLock()
  })

  it('remembers a list that closes before the lock click lands', () => {
    let open = false
    stops.push(
      registerTrainingUiLock({
        key: 'mindgraph-language',
        isOpen: () => open,
        setOpen: (next) => {
          open = next
        },
      })
    )
    open = true
    armTrainingUiLock()
    open = false
    expect(captureOpenTrainingUiLock()).toBeNull()
    expect(takeArmedTrainingUiLock()).toBe('mindgraph-language')
  })

  it('opens a list that mounts after the step is applied, then forgets it', () => {
    const seen: boolean[] = []
    applyTrainingUiLock('mindgraph-language')
    stops.push(
      registerTrainingUiLock({
        key: 'mindgraph-language',
        isOpen: () => false,
        setOpen: (next) => {
          seen.push(next)
        },
      })
    )
    expect(seen).toEqual([true])
    releaseTrainingUiLock()
    const later: boolean[] = []
    stops.push(
      registerTrainingUiLock({
        key: 'mindgraph-language',
        isOpen: () => false,
        setOpen: (next) => {
          later.push(next)
        },
      })
    )
    expect(later).toEqual([])
  })

  it('applies a lock only inside the deck shell that is on screen', () => {
    const outer: boolean[] = []
    const inner: boolean[] = []
    stops.push(
      registerTrainingUiLock({
        key: 'user-dropdown',
        isOpen: () => false,
        setOpen: (next) => {
          outer.push(next)
        },
      })
    )
    stops.push(
      registerTrainingUiLock({
        key: 'user-dropdown',
        scope: 'deck-a',
        isOpen: () => true,
        setOpen: (next) => {
          inner.push(next)
        },
      })
    )
    const releaseScope = pushTrainingLockScope('deck-a')
    stops.push(releaseScope)
    expect(captureOpenTrainingUiLock()).toBe('user-dropdown')
    applyTrainingUiLock(null)
    expect(outer).toEqual([])
    expect(inner).toEqual([false])
  })
})
