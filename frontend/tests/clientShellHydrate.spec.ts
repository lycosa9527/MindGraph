import { describe, expect, it } from 'vitest'

import { planClientShellHydrate } from '@/stores/clientShellState'

describe('planClientShellHydrate', () => {
  it('applies the server shell when this page has not chosen', () => {
    expect(planClientShellHydrate(0, 0, 'mobile', null)).toBe('apply-remote')
    expect(planClientShellHydrate(0, 0, 'desktop', 'mobile')).toBe('apply-remote')
  })

  it('uploads a local lock when the server has no row', () => {
    expect(planClientShellHydrate(0, 0, 'missing', 'desktop')).toBe('upload-local')
    expect(planClientShellHydrate(0, 0, 'missing', null)).toBe('ignore')
  })

  it('leaves an in-flight choice alone', () => {
    expect(planClientShellHydrate(0, 1, 'mobile', 'desktop')).toBe('ignore')
    expect(planClientShellHydrate(1, 1, 'mobile', 'desktop')).toBe('ignore')
  })

  it('keeps the local lock when the server cannot be read', () => {
    expect(planClientShellHydrate(0, 0, 'unavailable', 'desktop')).toBe('ignore')
  })
})
