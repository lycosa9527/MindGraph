/**
 * Desktop side of the 演讲模式 watch clicker: publish HUD, drain commands.
 * Start is accepted while idle so the watch can open a library diagram into slides.
 * Commands arrive via WebSocket wake + instant LPOP. HUD is published only when
 * it changes. Redis TTL is refreshed by the desktop socket, not an HTTP timer.
 */
import { onUnmounted, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { bindSlideRemoteWakeDrain } from '@/composables/mindMap/bindSlideRemoteWakeDrain'
import type { useMindMapSlidePresentation } from '@/composables/mindMap/useMindMapSlidePresentation'
import { applySlideRemoteCommand } from '@/utils/applySlideRemoteCommand'
import {
  drainSlideRemoteCommands,
  endSlideRemoteSession,
  publishSlideRemoteSession,
} from '@/utils/slideRemoteApi'
import {
  clearSlideRemoteCanvasDrain,
  touchSlideRemoteCanvasDrain,
} from '@/utils/slideRemoteCanvasDrainLock'
import {
  consumeSlideRemotePendingStart,
  peekSlideRemotePendingStart,
  setSlideRemotePendingStart,
  shouldJumpForSlideRemoteStart,
} from '@/utils/slideRemotePendingStart'

type SlidePresentation = ReturnType<typeof useMindMapSlidePresentation>

export function useSlideRemote(options: {
  slidesActive: () => boolean
  slidePresentation: SlidePresentation
  diagramId: () => string | null
  title: () => string
  openDiagram: (diagramId: string) => Promise<void> | void
  enterSlides: () => void
  exitPresentation: () => void
}): void {
  let inFlight = false
  let opened = false

  function enterIfPending(): void {
    const pending = peekSlideRemotePendingStart()
    if (!pending) return
    const current = options.diagramId()?.trim() ?? ''
    if (current !== pending) return
    if (!consumeSlideRemotePendingStart(pending)) return
    options.enterSlides()
  }

  function startSlides(diagramId: string): void {
    const target = diagramId.trim()
    if (!target) return
    setSlideRemotePendingStart(target)
    if (shouldJumpForSlideRemoteStart(options.diagramId(), target)) {
      void options.openDiagram(target)
      return
    }
    enterIfPending()
  }

  function handlers() {
    const slides = options.slidePresentation
    return {
      nextSlide: () => slides.nextSlide(),
      prevSlide: () => slides.prevSlide(),
      toggleAutoPlay: () => slides.toggleAutoPlay(),
      autoPlay: slides.autoPlay.value,
      setTraversalMode: slides.setTraversalMode,
      exitSlideShow: () => options.exitPresentation(),
      startSlides,
    }
  }

  async function publish(): Promise<void> {
    if (!options.slidesActive()) return
    const slides = options.slidePresentation
    await publishSlideRemoteSession({
      diagram_id: options.diagramId() ?? '',
      title: options.title(),
      slide_index: slides.slideIndex.value,
      slide_count: slides.slideCount.value,
      traversal: slides.traversalMode.value,
      autoplay: slides.autoPlay.value,
      can_prev: slides.canGoPrev.value,
      can_next: slides.canGoNext.value,
    })
    opened = true
  }

  async function drain(): Promise<void> {
    if (inFlight) return
    inFlight = true
    touchSlideRemoteCanvasDrain()
    try {
      const items = await drainSlideRemoteCommands()
      for (const row of items) {
        applySlideRemoteCommand(row, handlers())
      }
    } finally {
      inFlight = false
    }
  }

  const wake = bindSlideRemoteWakeDrain({
    drain,
    shouldRun: () => true,
  })

  async function stopPublish(): Promise<void> {
    if (!opened) return
    opened = false
    try {
      await endSlideRemoteSession()
    } catch {
      /* tab may already be gone */
    }
  }

  watch(
    () => {
      const slides = options.slidePresentation
      return [
        options.slidesActive(),
        options.diagramId(),
        options.title(),
        slides.slideIndex.value,
        slides.slideCount.value,
        slides.traversalMode.value,
        slides.autoPlay.value,
        slides.canGoPrev.value,
        slides.canGoNext.value,
      ] as const
    },
    (current) => {
      wake.start()
      if (!current[0]) {
        void stopPublish()
        return
      }
      void publish()
    },
    { immediate: true }
  )

  const stopLoaded = eventBus.on('diagram:loaded_from_library', (payload) => {
    const pending = peekSlideRemotePendingStart()
    if (pending && payload.diagramId === pending) {
      enterIfPending()
    }
  })

  enterIfPending()

  onUnmounted(() => {
    stopLoaded()
    clearSlideRemoteCanvasDrain()
    wake.stop()
    if (opened) {
      void endSlideRemoteSession()
      opened = false
    }
  })
}
