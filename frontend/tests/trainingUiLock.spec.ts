import { afterEach, describe, expect, it } from 'vitest'

import {
  applyTrainingUiLock,
  armTrainingUiLock,
  captureOpenTrainingUiLock,
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
})
