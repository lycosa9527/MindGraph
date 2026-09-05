import { describe, expect, it, vi } from 'vitest'

import {
  isTrainingMediaStep,
  shouldAwakeOnSelect,
  shouldRecaptureThumb,
} from '@/composables/training/trainingBuilderHibernate'
import { blankPageStep, blankSlideStep } from '@/composables/training/trainingBuilderSteps'
import {
  dataUrlToPngFile,
  isPersistedTrainingThumb,
} from '@/composables/training/persistTrainingThumb'
import {
  captureTrainingStage,
  raceCapture,
  trainingStepPageKey,
  trainingStepThumbKey,
} from '@/composables/training/trainingStageThumb'

describe('trainingStageThumb', () => {
  it('changes the thumb key when overlays or page targets change', () => {
    const step = blankPageStep(0)
    const before = trainingStepThumbKey(step)
    const pageBefore = trainingStepPageKey(step)
    step.focus_key = 'auth-register'
    step.overlays = [{ kind: 'text', x: 20, y: 18, text: '注册' }]
    expect(trainingStepThumbKey(step)).not.toBe(before)
    expect(trainingStepPageKey(step)).not.toBe(pageBefore)
    expect(trainingStepThumbKey(null)).toBe('')
  })

  it('keeps the page key stable when only overlays move', () => {
    const step = blankPageStep(0)
    const pageBefore = trainingStepPageKey(step)
    step.overlays = [{ kind: 'text', x: 20, y: 18, text: '注册' }]
    expect(trainingStepPageKey(step)).toBe(pageBefore)
  })

  it('returns no snapshot when the builder stage is missing', async () => {
    document.body.innerHTML = ''
    await expect(captureTrainingStage()).resolves.toBeNull()
  })

  it('gives up when a stage snapshot never resolves', async () => {
    vi.useFakeTimers()
    const pending = raceCapture(new Promise<string>(() => undefined), 1200)
    await vi.advanceTimersByTimeAsync(1200)
    await expect(pending).resolves.toBeNull()
    vi.useRealTimers()
  })
})

describe('training builder hibernate', () => {
  it('wakes page slides so the filmstrip stays tied to the live stage', () => {
    const step = blankPageStep(0)
    expect(shouldAwakeOnSelect(step)).toBe(true)
    expect(shouldAwakeOnSelect(null)).toBe(true)
  })

  it('never wakes a media slide and skips recapture while asleep', () => {
    const image = blankSlideStep(0)
    image.asset_url = '/api/training/assets/courses/x/slides/a.png'
    expect(isTrainingMediaStep(image)).toBe(true)
    expect(shouldAwakeOnSelect(image)).toBe(false)
    expect(shouldRecaptureThumb(null, '', image, true)).toBe(false)
    expect(
      shouldRecaptureThumb('data:image/png;base64,xx', 'page|mindgraph', blankPageStep(0), false)
    ).toBe(false)
  })

  it('treats COS asset URLs as persisted previews', () => {
    expect(isPersistedTrainingThumb('data:image/png;base64,xx')).toBe(false)
    expect(isPersistedTrainingThumb('/api/training/assets/courses/x/thumbs/a.png')).toBe(true)
  })

  it('decodes a PNG data URL without fetch (CSP connect-src blocks data:)', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const pixel =
      'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
    const file = dataUrlToPngFile(pixel, 'slide-1.png')
    expect(file.name).toBe('slide-1.png')
    expect(file.type).toBe('image/png')
    expect(file.size).toBeGreaterThan(0)
    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })

  it('rejects a data URL with no payload', () => {
    expect(() => dataUrlToPngFile('not-a-data-url', 'slide-1.png')).toThrow('invalid data url')
  })

  it('recaptures when the live page or its marks change', () => {
    const step = blankPageStep(0)
    const key = trainingStepThumbKey(step)
    expect(shouldRecaptureThumb('data:image/png;base64,xx', key, step, true)).toBe(false)
    step.focus_key = 'auth-register'
    expect(shouldRecaptureThumb('data:image/png;base64,xx', key, step, true)).toBe(true)
    step.focus_key = null
    expect(shouldRecaptureThumb('data:image/png;base64,xx', key, step, true)).toBe(false)
    step.overlays = [{ kind: 'text', x: 20, y: 18, text: '注册' }]
    expect(shouldRecaptureThumb('data:image/png;base64,xx', key, step, true)).toBe(true)
  })
})
