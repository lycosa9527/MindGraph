import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it } from 'vitest'

import { blankPageStep } from '@/composables/training/trainingBuilderSteps'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import type { TrainingCourse } from '@/types/training'

function course(overrides: Partial<TrainingCourse> = {}): TrainingCourse {
  return {
    id: 'course-1',
    title: '双气泡',
    description: '对比',
    status: 'ready',
    is_system: false,
    steps: [blankPageStep(0), blankPageStep(1)],
    ...overrides,
  }
}

describe('trainingBuilder store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('loads the course document and seeds a blank slide when empty', () => {
    const store = useTrainingBuilderStore()
    store.applyCourse(course())
    expect(store.title).toBe('双气泡')
    expect(store.steps).toHaveLength(2)
    expect(store.current?.page_key).toBe('mindgraph')
    store.applyCourse(course({ steps: [] }))
    expect(store.steps).toHaveLength(1)
    expect(store.selected).toBe(0)
  })

  it('keeps selection in range when a slide is removed', () => {
    const store = useTrainingBuilderStore()
    store.applyCourse(course())
    store.setSelected(1)
    store.removeStepAt(1)
    expect(store.steps).toHaveLength(1)
    expect(store.selected).toBe(0)
  })

  it('inserts image slides at the current index', () => {
    const store = useTrainingBuilderStore()
    store.applyCourse(course())
    store.setSelected(0)
    store.insertCreatedSteps(0, [
      {
        ...blankPageStep(0),
        type: 'slide',
        asset_id: 'a1',
        asset_url: '/api/training/assets/a.png',
      },
    ])
    expect(store.steps).toHaveLength(3)
    expect(store.selected).toBe(0)
    expect(store.steps[0].asset_id).toBe('a1')
    expect(store.thumbs[0]).toBe('/api/training/assets/a.png')
  })

  it('lets authors edit the seeded system course', () => {
    const store = useTrainingBuilderStore()
    store.applyCourse(course({ is_system: true, title: '种子' }))
    expect(store.isSystem).toBe(true)
    store.setTitle('改掉')
    store.pushBlankPage()
    expect(store.title).toBe('改掉')
    expect(store.steps).toHaveLength(3)
    store.removeStepAt(2)
    expect(store.steps).toHaveLength(2)
  })

  it('resets the draft when leaving the editor', () => {
    const store = useTrainingBuilderStore()
    store.applyCourse(course())
    store.setTitle('keep')
    store.setPreviewing(true)
    store.reset()
    expect(store.title).toBe('')
    expect(store.steps).toHaveLength(0)
    expect(store.previewing).toBe(false)
  })
})
