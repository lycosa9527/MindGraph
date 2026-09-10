import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it } from 'vitest'

import { useDiagramTranslateUiStore } from '@/stores/diagramTranslateUi'

describe('diagramTranslateUi pending snapshot', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('keeps target language and diagram JSON only until cleared', () => {
    const store = useDiagramTranslateUiStore()
    expect(store.hasPendingTranslate).toBe(false)

    store.armPending('ja', { type: 'mindmap', nodes: [{ id: 'n1', text: '光' }] })
    store.setPhase('streaming')
    store.setTranslatedSpec({ type: 'mindmap', nodes: [{ id: 'n1', text: 'Light' }] })
    expect(store.hasPendingTranslate).toBe(true)
    expect(store.viewingTranslated).toBe(false)
    expect(store.phase).toBe('streaming')
    expect(store.pendingTargetLanguage).toBe('ja')
    expect(store.pendingSourceSpec).toEqual({
      type: 'mindmap',
      nodes: [{ id: 'n1', text: '光' }],
    })

    const firstGen = store.streamGeneration
    store.beginStream()
    expect(store.streamGeneration).toBe(firstGen + 1)
    expect(store.isCurrentGeneration(firstGen)).toBe(false)
    expect(store.isCurrentGeneration(firstGen + 1)).toBe(true)

    const genAfterBegin = store.streamGeneration
    store.abortTranslate()
    expect(store.isCurrentGeneration(genAfterBegin)).toBe(false)
    expect(store.hasPendingTranslate).toBe(false)
    expect(store.pendingTargetLanguage).toBeNull()
    expect(store.pendingSourceSpec).toBeNull()
    expect(store.translatedSpec).toBeNull()
    expect(store.viewingTranslated).toBe(false)
    expect(store.phase).toBe('idle')
    expect(store.inFlight).toBe(false)
  })

  it('invalidates an in-flight generation without clearing the pending snapshot', () => {
    const store = useDiagramTranslateUiStore()
    store.armPending('ko', { type: 'mindmap', nodes: [{ id: 'n1', text: '빛' }] })
    store.setInFlight(true)
    store.beginStream()
    const generation = store.streamGeneration

    store.invalidateInFlight()

    expect(store.isCurrentGeneration(generation)).toBe(false)
    expect(store.inFlight).toBe(false)
    expect(store.hasPendingTranslate).toBe(true)
    expect(store.pendingTargetLanguage).toBe('ko')
  })

  it('keeps viewingTranslated across a new language arm so persist stays on the original', () => {
    const store = useDiagramTranslateUiStore()
    store.armPending('en', { type: 'mindmap', topic: '光' })
    store.setViewingTranslated(true)
    store.armPending('ja', { type: 'mindmap', topic: '光' })
    expect(store.viewingTranslated).toBe(true)
    expect(store.pendingTargetLanguage).toBe('ja')
    expect(store.translatedSpec).toBeNull()
  })
})
