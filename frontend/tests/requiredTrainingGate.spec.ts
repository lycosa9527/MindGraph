import { describe, expect, it } from 'vitest'

import { shouldSkipRequiredTraining } from '@/utils/requiredTrainingGate'

describe('required training gate', () => {
  it('lets authors, admins, and the tutorial itself through', () => {
    expect(shouldSkipRequiredTraining('/auth')).toBe(true)
    expect(shouldSkipRequiredTraining('/training/required')).toBe(true)
    expect(shouldSkipRequiredTraining('/training/builder/abc')).toBe(true)
    expect(shouldSkipRequiredTraining('/admin')).toBe(true)
  })

  it('blocks ordinary app routes until the course is finished', () => {
    expect(shouldSkipRequiredTraining('/mindmate')).toBe(false)
    expect(shouldSkipRequiredTraining('/canvas')).toBe(false)
    expect(shouldSkipRequiredTraining('/training')).toBe(false)
  })
})
