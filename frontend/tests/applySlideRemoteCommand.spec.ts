import { describe, expect, it, vi } from 'vitest'

import { applySlideRemoteCommand } from '@/utils/applySlideRemoteCommand'

function handlers() {
  return {
    nextSlide: vi.fn(),
    prevSlide: vi.fn(),
    toggleAutoPlay: vi.fn(),
    autoPlay: false,
    setTraversalMode: vi.fn(),
    exitSlideShow: vi.fn(),
    startSlides: vi.fn(),
  }
}

describe('applySlideRemoteCommand', () => {
  it('steps next and previous', () => {
    const api = handlers()
    applySlideRemoteCommand({ action: 'next' }, api)
    applySlideRemoteCommand({ action: 'prev' }, api)
    expect(api.nextSlide).toHaveBeenCalledOnce()
    expect(api.prevSlide).toHaveBeenCalledOnce()
  })

  it('quits the slide show', () => {
    const api = handlers()
    applySlideRemoteCommand({ action: 'quit' }, api)
    expect(api.exitSlideShow).toHaveBeenCalledOnce()
  })

  it('starts slides for a library diagram', () => {
    const api = handlers()
    applySlideRemoteCommand({ action: 'start' }, api)
    applySlideRemoteCommand({ action: 'start', diagram_id: 'diag-9' }, api)
    expect(api.startSlides).toHaveBeenCalledOnce()
    expect(api.startSlides).toHaveBeenCalledWith('diag-9')
  })

  it('sets traversal when the mode is known', () => {
    const api = handlers()
    applySlideRemoteCommand({ action: 'traversal', mode: 'deep' }, api)
    applySlideRemoteCommand({ action: 'traversal' }, api)
    expect(api.setTraversalMode).toHaveBeenCalledOnce()
    expect(api.setTraversalMode).toHaveBeenCalledWith('deep')
  })

  it('toggles autoplay only when the desired state differs', () => {
    const api = handlers()
    applySlideRemoteCommand({ action: 'autoplay', on: false }, api)
    expect(api.toggleAutoPlay).not.toHaveBeenCalled()
    applySlideRemoteCommand({ action: 'autoplay', on: true }, api)
    expect(api.toggleAutoPlay).toHaveBeenCalledOnce()
    applySlideRemoteCommand({ action: 'autoplay' }, api)
    expect(api.toggleAutoPlay).toHaveBeenCalledTimes(2)
  })
})
