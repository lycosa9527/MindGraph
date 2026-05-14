import { describe, expect, it } from 'vitest'

import {
  type ConceptMapPillEstimateRole,
  estimateConceptMapPillFootprintPx,
} from '@/utils/cmapConceptPillEstimate'

describe('estimateConceptMapPillFootprintPx', () => {
  it('grows footprint for longer labels (Latin)', () => {
    const shortFx = estimateConceptMapPillFootprintPx('ab', 'branch')
    const longFx = estimateConceptMapPillFootprintPx('abcdefghijklmnop', 'branch')
    expect(longFx.halfWidth).toBeGreaterThanOrEqual(shortFx.halfWidth)
  })

  it('uses wider heuristic for Han script strings', () => {
    const han = estimateConceptMapPillFootprintPx('同化学习原理概述', 'branch')
    const latinSameLen = estimateConceptMapPillFootprintPx('abcdefghij', 'branch')
    expect(han.halfWidth).toBeGreaterThanOrEqual(latinSameLen.halfWidth)
  })

  it('topics get larger caps than branches for comparable text', () => {
    const text = 'Focus question text'
    const topic = estimateConceptMapPillFootprintPx(text, 'topic')
    const branch = estimateConceptMapPillFootprintPx(text, 'branch')
    expect(topic.halfHeight).toBeGreaterThanOrEqual(branch.halfHeight)
    expect(topic.halfWidth).toBeGreaterThanOrEqual(branch.halfWidth)
  })

  it('caps half-width regardless of exaggerated length', () => {
    const huge = estimateConceptMapPillFootprintPx('x'.repeat(400), 'branch')
    expect(huge.halfWidth).toBeLessThanOrEqual(250)
    const hugeTopic = estimateConceptMapPillFootprintPx('汉'.repeat(200), 'topic')
    expect(hugeTopic.halfWidth).toBeLessThanOrEqual(295)
  })

  const roles: ConceptMapPillEstimateRole[] = ['topic', 'branch']
  it.each(roles)('respects sensible minimum footprints for role %s', (role) => {
    const f = estimateConceptMapPillFootprintPx('a', role)
    expect(f.halfWidth).toBeGreaterThanOrEqual(35)
    expect(f.halfHeight).toBeGreaterThanOrEqual(16)
  })
})
