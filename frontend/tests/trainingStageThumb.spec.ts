import { describe, expect, it } from 'vitest'

import {
  isTrainingMediaStep,
  shouldAwakeOnSelect,
  shouldRecaptureThumb,
} from '@/composables/training/trainingBuilderHibernate'
import { blankPageStep, blankSlideStep } from '@/composables/training/trainingBuilderSteps'
import { isPersistedTrainingThumb } from '@/composables/training/persistTrainingThumb'
import {
  captureTrainingStage,
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
})

describe('training builder hibernate', () => {
  it('stays asleep on a slide that already has a snapshot', () => {
    const step = blankPageStep(0)
    expect(shouldAwakeOnSelect('data:image/png;base64,xx', step)).toBe(false)
    expect(shouldAwakeOnSelect(null, step)).toBe(true)
  })

  it('never wakes a media slide and skips recapture while asleep', () => {
    const image = blankSlideStep(0)
    image.asset_url = '/api/training/assets/courses/x/slides/a.png'
    expect(isTrainingMediaStep(image)).toBe(true)
    expect(shouldAwakeOnSelect(null, image)).toBe(false)
    expect(shouldRecaptureThumb(null, '', image, true)).toBe(false)
    expect(shouldRecaptureThumb('data:image/png;base64,xx', 'page|mindgraph', blankPageStep(0), false)).toBe(
      false
    )
  })

  it('treats COS asset URLs as persisted previews', () => {
    expect(isPersistedTrainingThumb('data:image/png;base64,xx')).toBe(false)
    expect(isPersistedTrainingThumb('/api/training/assets/courses/x/thumbs/a.png')).toBe(true)
  })

  it('recaptures only when the live page itself changed', () => {
    const step = blankPageStep(0)
    const key = trainingStepPageKey(step)
    expect(shouldRecaptureThumb('data:image/png;base64,xx', key, step, true)).toBe(false)
    step.focus_key = 'auth-register'
    expect(shouldRecaptureThumb('data:image/png;base64,xx', key, step, true)).toBe(true)
  })
})
