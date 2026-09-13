import { createApp, defineComponent, ref } from 'vue'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import { useSlideRemote } from '@/composables/mindMap/useSlideRemote'
import { peekSlideRemotePendingStart } from '@/utils/slideRemotePendingStart'

const drainMock = vi.hoisted(() => vi.fn().mockResolvedValue([]))

vi.mock('@/utils/slideRemoteApi', () => ({
  drainSlideRemoteCommands: (...args: unknown[]) => drainMock(...args),
  publishSlideRemoteSession: vi.fn().mockResolvedValue(null),
  endSlideRemoteSession: vi.fn().mockResolvedValue(undefined),
}))

function slidePresentation() {
  return {
    nextSlide: vi.fn(),
    prevSlide: vi.fn(),
    toggleAutoPlay: vi.fn(),
    autoPlay: ref(false),
    setTraversalMode: vi.fn(),
    slideIndex: ref(0),
    slideCount: ref(0),
    traversalMode: ref('firstLevel' as const),
    canGoPrev: ref(false),
    canGoNext: ref(false),
    currentSlide: ref(null),
  }
}

function mountRemote(options: {
  diagramId: () => string | null
  openDiagram: (id: string) => void
  enterSlides: () => void
}) {
  const app = createApp(
    defineComponent({
      setup() {
        useSlideRemote({
          slidesActive: () => false,
          slidePresentation: slidePresentation() as never,
          diagramId: options.diagramId,
          title: () => '',
          openDiagram: options.openDiagram,
          enterSlides: options.enterSlides,
          exitPresentation: vi.fn(),
        })
        return () => null
      },
    })
  )
  app.mount(document.createElement('div'))
  return () => app.unmount()
}

describe('useSlideRemote start jump', () => {
  beforeEach(() => {
    sessionStorage.clear()
    localStorage.clear()
    drainMock.mockReset()
    drainMock.mockResolvedValue([])
  })

  afterEach(() => {
    sessionStorage.clear()
    localStorage.clear()
  })

  it('opens the library diagram and waits for the load event before slides', async () => {
    const openDiagram = vi.fn()
    const enterSlides = vi.fn()
    drainMock.mockResolvedValueOnce([{ action: 'start', diagram_id: 'diag-2' }])
    const stop = mountRemote({
      diagramId: () => 'diag-1',
      openDiagram,
      enterSlides,
    })
    await vi.waitFor(() => {
      expect(openDiagram).toHaveBeenCalledWith('diag-2')
    })
    expect(enterSlides).not.toHaveBeenCalled()
    expect(peekSlideRemotePendingStart()).toBe('diag-2')
    eventBus.emit('diagram:loaded_from_library', {
      diagramId: 'diag-2',
      diagramType: 'mindmap',
    })
    expect(enterSlides).not.toHaveBeenCalled()
    stop()
  })

  it('enters slides when the pending diagram finishes loading', async () => {
    const openDiagram = vi.fn()
    const enterSlides = vi.fn()
    const diagramId = { value: 'diag-1' }
    drainMock.mockResolvedValueOnce([{ action: 'start', diagram_id: 'diag-2' }])
    const stop = mountRemote({
      diagramId: () => diagramId.value,
      openDiagram,
      enterSlides,
    })
    await vi.waitFor(() => {
      expect(openDiagram).toHaveBeenCalledWith('diag-2')
    })
    diagramId.value = 'diag-2'
    eventBus.emit('diagram:loaded_from_library', {
      diagramId: 'diag-2',
      diagramType: 'mindmap',
    })
    expect(enterSlides).toHaveBeenCalledOnce()
    stop()
  })

  it('starts slides immediately when the canvas already has that diagram', async () => {
    const openDiagram = vi.fn()
    const enterSlides = vi.fn()
    drainMock.mockResolvedValueOnce([{ action: 'start', diagram_id: 'diag-1' }])
    const stop = mountRemote({
      diagramId: () => 'diag-1',
      openDiagram,
      enterSlides,
    })
    await vi.waitFor(() => {
      expect(enterSlides).toHaveBeenCalledOnce()
    })
    expect(openDiagram).not.toHaveBeenCalled()
    stop()
  })
})
