import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'

import { useMindMateStore } from '@/stores/mindmate'

describe('useMindMateStore loadPhase', () => {
  it('tracks generating state and resets on resetLoadPhase', () => {
    setActivePinia(createPinia())
    const store = useMindMateStore()

    expect(store.loadPhase).toBe('idle')
    expect(store.isGenerating).toBe(false)

    store.setLoadPhase('waiting')
    expect(store.loadPhase).toBe('waiting')
    expect(store.isGenerating).toBe(true)

    store.resetLoadPhase()
    expect(store.loadPhase).toBe('idle')
    expect(store.isGenerating).toBe(false)
  })

  it('clears loadPhase on store reset', () => {
    setActivePinia(createPinia())
    const store = useMindMateStore()
    store.setLoadPhase('streaming')
    store.setActiveThread('conv-1', [
      { id: 'm1', role: 'user', content: 'hi', timestamp: 1 },
    ], true)
    store.reset()
    expect(store.loadPhase).toBe('idle')
    expect(store.activeThreadMessages).toHaveLength(0)
  })
})
