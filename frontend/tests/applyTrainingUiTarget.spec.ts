import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { applyTrainingUiTarget, queryTrainingFocus } from '@/composables/training/applyTrainingUiTarget'
import { registerTrainingUiHost } from '@/composables/training/trainingUiBridge'
import { useTrainingStore } from '@/stores/training'

describe('applyTrainingUiTarget', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
  })

  it('opens the catalogued modal then rings the button', async () => {
    const opened: string[] = []
    const closed: string[] = []
    registerTrainingUiHost({
      openModal: (key) => {
        opened.push(key)
        const button = document.createElement('button')
        button.setAttribute('data-training-target', 'mindmap-v2')
        document.body.appendChild(button)
      },
      closeModals: () => {
        closed.push('all')
      },
    })
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
    registerTrainingUiHost({
      openModal: vi.fn(),
      closeModals: vi.fn(),
    })
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
    registerTrainingUiHost({
      openModal: vi.fn(),
      closeModals: vi.fn(),
    })
    await applyTrainingUiTarget({ modalKey: null, focusKey: 'diagram-double_bubble_map' })
    expect(clicked).not.toHaveBeenCalled()
    expect(useTrainingStore().uiFocusKey).toBe('diagram-double_bubble_map')
  })

  it('closes app modals when the slide has no modal', async () => {
    const closeModals = vi.fn()
    registerTrainingUiHost({
      openModal: vi.fn(),
      closeModals,
    })
    await applyTrainingUiTarget({ modalKey: null, focusKey: null })
    expect(closeModals).toHaveBeenCalled()
    expect(useTrainingStore().uiFocusKey).toBeNull()
  })
})
