import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import { applyTrainingUiTarget, queryTrainingFocus } from '@/composables/training/applyTrainingUiTarget'
import { useTrainingStore } from '@/stores/training'

describe('applyTrainingUiTarget', () => {
  const opened: string[] = []
  const closed: string[] = []

  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
    opened.length = 0
    closed.length = 0
    eventBus.on('training:modal_open_requested', ({ key }) => {
      opened.push(key)
      if (key === 'language-settings') {
        const button = document.createElement('button')
        button.setAttribute('data-training-target', 'mindmap-v2')
        document.body.appendChild(button)
      }
    })
    eventBus.on('training:modal_close_requested', () => {
      closed.push('all')
    })
  })

  afterEach(() => {
    eventBus.off('training:modal_open_requested')
    eventBus.off('training:modal_close_requested')
  })

  it('opens the catalogued modal then rings the button', async () => {
    await applyTrainingUiTarget({
      modalKey: 'language-settings',
      focusKey: 'mindmap-v2',
    })
    expect(opened).toEqual(['language-settings'])
    expect(closed).toEqual([])
    expect(useTrainingStore().uiFocusKey).toBe('mindmap-v2')
    expect(queryTrainingFocus('mindmap-v2')?.getAttribute('data-training-target')).toBe(
      'mindmap-v2'
    )
  })

  it('clicks auth tabs so the live form switches', async () => {
    const tab = document.createElement('button')
    tab.setAttribute('data-training-target', 'auth-register')
    const clicked = vi.fn()
    tab.addEventListener('click', clicked)
    document.body.appendChild(tab)
    await applyTrainingUiTarget({ modalKey: null, focusKey: 'auth-register' })
    expect(clicked).toHaveBeenCalled()
    expect(useTrainingStore().uiFocusKey).toBe('auth-register')
  })

  it('does not click landing cards when applying focus', async () => {
    const card = document.createElement('div')
    card.setAttribute('data-training-target', 'diagram-double_bubble_map')
    const clicked = vi.fn()
    card.addEventListener('click', clicked)
    document.body.appendChild(card)
    await applyTrainingUiTarget({ modalKey: null, focusKey: 'diagram-double_bubble_map' })
    expect(clicked).not.toHaveBeenCalled()
    expect(useTrainingStore().uiFocusKey).toBe('diagram-double_bubble_map')
  })

  it('closes app modals when the slide has no modal', async () => {
    await applyTrainingUiTarget({ modalKey: null, focusKey: null })
    expect(closed).toEqual(['all'])
    expect(useTrainingStore().uiFocusKey).toBeNull()
  })
})
