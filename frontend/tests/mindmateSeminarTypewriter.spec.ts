import { describe, expect, it } from 'vitest'

import { createSeminarTypewriter } from '@/utils/mindmateSeminarTypewriter'

describe('seminar typewriter', () => {
  it('types a phrase one character at a time', () => {
    const paints: string[] = []
    const queued: Array<() => void> = []
    let done = 0
    const writer = createSeminarTypewriter({
      onPaint: (visible) => {
        paints.push(visible)
      },
      onDone: () => {
        done += 1
      },
      schedule: (run) => {
        queued.push(run)
        return () => {
          const index = queued.indexOf(run)
          if (index >= 0) {
            queued.splice(index, 1)
          }
        }
      },
    })

    writer.push('师们好')
    expect(paints).toEqual(['师'])
    queued.shift()?.()
    queued.shift()?.()
    expect(paints).toEqual(['师', '师们', '师们好'])
    expect(done).toBe(0)

    writer.seal('师们好')
    expect(done).toBe(1)
    expect(queued).toHaveLength(0)
  })

  it('types an emoji as one step', () => {
    const paints: string[] = []
    const queued: Array<() => void> = []
    const writer = createSeminarTypewriter({
      onPaint: (visible) => {
        paints.push(visible)
      },
      onDone: () => undefined,
      schedule: (run) => {
        queued.push(run)
        return () => undefined
      },
    })
    writer.push('A😀')
    expect(paints).toEqual(['A'])
    queued.shift()?.()
    expect(paints[1]).toBe('A😀')
  })
})
