import { describe, expect, it, vi } from 'vitest'

import {
  flushCanvasBeforeLibrarySwitch,
  shouldFlushBeforeLibrarySwitch,
} from '@/composables/canvasPage/shouldFlushBeforeLibrarySwitch'

describe('shouldFlushBeforeLibrarySwitch', () => {
  it('flushes when the canvas is dirty', () => {
    expect(shouldFlushBeforeLibrarySwitch({ isDirty: true, isGenerating: false })).toBe(true)
  })

  it('flushes during auto-complete even after the first model cleared isDirty', () => {
    expect(shouldFlushBeforeLibrarySwitch({ isDirty: false, isGenerating: true })).toBe(true)
  })

  it('skips a new PUT after generation has persisted', () => {
    expect(shouldFlushBeforeLibrarySwitch({ isDirty: false, isGenerating: false })).toBe(false)
  })
})

describe('flushCanvasBeforeLibrarySwitch', () => {
  it('always drains in-flight PUTs even when a new flush is skipped', async () => {
    const drainPersistQueue = vi.fn(async () => undefined)
    const flushOnLeave = vi.fn()
    await expect(
      flushCanvasBeforeLibrarySwitch({
        isDirty: false,
        isGenerating: false,
        drainPersistQueue,
        flushOnLeave,
        collabOwnsPersist: false,
      })
    ).resolves.toBe('ok')
    expect(drainPersistQueue).toHaveBeenCalledOnce()
    expect(flushOnLeave).not.toHaveBeenCalled()
  })

  it('drains then flushes while generating', async () => {
    const order: string[] = []
    await expect(
      flushCanvasBeforeLibrarySwitch({
        isDirty: false,
        isGenerating: true,
        drainPersistQueue: async () => {
          order.push('drain')
        },
        flushOnLeave: async () => {
          order.push('flush')
          return { saved: true, reason: 'success' }
        },
        collabOwnsPersist: false,
      })
    ).resolves.toBe('ok')
    expect(order).toEqual(['drain', 'flush'])
  })

  it('fails closed when leave flush does not persist', async () => {
    await expect(
      flushCanvasBeforeLibrarySwitch({
        isDirty: false,
        isGenerating: true,
        drainPersistQueue: async () => undefined,
        flushOnLeave: async () => ({ saved: false, reason: 'error' }),
        collabOwnsPersist: false,
      })
    ).resolves.toBe('failed')
  })

  it('allows collab to own durability when REST save is blocked', async () => {
    await expect(
      flushCanvasBeforeLibrarySwitch({
        isDirty: true,
        isGenerating: false,
        drainPersistQueue: async () => undefined,
        flushOnLeave: async () => ({ saved: false, reason: 'skipped_guards' }),
        collabOwnsPersist: true,
      })
    ).resolves.toBe('ok')
  })
})
