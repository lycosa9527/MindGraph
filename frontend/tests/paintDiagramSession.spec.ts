import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { resolvePaintDiagramSession } from '@/composables/diagram/useDiagramSession'
import { builderDiagramSession } from '@/composables/training/builderDiagramBridge'
import { asDiagramSession, createDiagramSession, useDiagramStore } from '@/stores/diagram'

function stubMatchMedia(): void {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({
      matches: false,
      media: '',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
  )
}

describe('resolvePaintDiagramSession', () => {
  beforeEach(() => {
    stubMatchMedia()
    setActivePinia(createPinia())
  })

  afterEach(() => {
    const published = builderDiagramSession.value
    builderDiagramSession.value = null
    published?.dispose()
  })

  it('uses the Pinia diagram store when the builder has no session', () => {
    expect(resolvePaintDiagramSession()).toBe(useDiagramStore())
  })

  it('uses the builder canvas session when it is published', () => {
    const session = asDiagramSession(
      createDiagramSession({
        mode: 'edit',
        vueFlowId: 'test-paint-session',
        emitDiagramEvents: false,
      })
    )
    builderDiagramSession.value = session
    expect(resolvePaintDiagramSession()).toBe(session)
    expect(resolvePaintDiagramSession()).not.toBe(useDiagramStore())
  })
})
