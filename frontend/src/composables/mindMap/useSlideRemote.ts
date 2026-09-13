/**
 * Desktop side of the 演讲模式 watch clicker: publish HUD, drain commands.
 * Start is accepted while idle so the watch can open a library diagram into slides.
 */
import { onUnmounted, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
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

const SNAPSHOT_MS = 2000
const DRAIN_MS = 400

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
  let snapshotTimer: ReturnType<typeof setInterval> | null = null
  let drainTimer: ReturnType<typeof setInterval> | null = null
  let inFlight = false
  let opened = false

  function clearSnapshotTimer(): void {
    if (snapshotTimer !== null) {
      clearInterval(snapshotTimer)
      snapshotTimer = null
    }
  }

  function clearDrainTimer(): void {
    if (drainTimer !== null) {
      clearInterval(drainTimer)
      drainTimer = null
    }
  }

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

  function startPublish(): void {
    clearSnapshotTimer()
    void publish()
    snapshotTimer = window.setInterval(() => {
      void publish()
    }, SNAPSHOT_MS)
  }

  function startListen(): void {
    if (drainTimer !== null) return
    void drain()
    drainTimer = window.setInterval(() => {
      void drain()
    }, DRAIN_MS)
  }

  async function stopPublish(): Promise<void> {
    clearSnapshotTimer()
    if (!opened) return
    opened = false
    try {
      await endSlideRemoteSession()
    } catch {
      /* tab may already be gone */
    }
  }

  watch(
    () => options.slidesActive(),
    (active) => {
      startListen()
      if (active) {
        startPublish()
        return
      }
      void stopPublish()
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
    clearSnapshotTimer()
    clearDrainTimer()
    if (opened) {
      void endSlideRemoteSession()
      opened = false
    }
  })
}
