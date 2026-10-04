import { afterEach, describe, expect, it } from 'vitest'

import { blankPageStep } from '@/composables/training/trainingBuilderSteps'
import {
  applyDeckPage,
  armTrainingDeckNavigation,
  consumeTrainingDeckNavigation,
  pushTrainingDeckSink,
  trainingPageFromLocation,
} from '@/composables/training/trainingDeckNav'

describe('trainingDeckNav', () => {
  const releases: Array<() => void> = []

  afterEach(() => {
    for (const release of releases) release()
    releases.length = 0
    consumeTrainingDeckNavigation('/mindgraph', null)
  })

  it('maps a gallery card click to the circle canvas', () => {
    expect(trainingPageFromLocation('/canvas', 'circle_map')).toEqual({
      pageKey: 'canvas',
      diagramType: 'circle_map',
    })
    expect(trainingPageFromLocation('/mindgraph', null)).toEqual({
      pageKey: 'mindgraph',
      diagramType: null,
    })
    expect(trainingPageFromLocation('/admin', null)).toBeNull()
  })

  it('sends Back to the gallery without leaving the slide', () => {
    const step = blankPageStep(0)
    applyDeckPage(step, 'canvas', 'circle_map')
    expect(step.page_key).toBe('canvas')
    expect(step.diagram_type).toBe('circle_map')
    applyDeckPage(step, 'mindgraph', null)
    expect(step.page_key).toBe('mindgraph')
    expect(step.diagram_type).toBeNull()
    expect(step.type).toBe('page')
  })

  it('keeps the click armed until the router guard, then drops it', async () => {
    const seen: string[] = []
    releases.push(
      pushTrainingDeckSink((target) => {
        seen.push(target.pageKey)
      })
    )
    armTrainingDeckNavigation()
    await Promise.resolve()
    expect(consumeTrainingDeckNavigation('/canvas', 'circle_map')).toBe(true)
    expect(seen).toEqual(['canvas'])
    await new Promise((resolve) => {
      window.setTimeout(resolve, 0)
    })
    expect(consumeTrainingDeckNavigation('/canvas', 'circle_map')).toBe(false)
  })
})
