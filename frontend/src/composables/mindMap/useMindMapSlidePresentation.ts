/**
 * Mind map slide presentation: overview + branches, auto-play, keyboard nav.
 */
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import {
  MIND_MAP_SLIDE_TRANSITION_MS,
  emitMindMapSlideViewportFit,
} from '@/composables/mindMap/emitMindMapSlideViewportFit'
import { waitForMindMapSlidePlayReady } from '@/composables/mindMap/waitForMindMapSlidePlayReady'
import { useDiagramStore } from '@/stores'
import { setMindMapCollapsedPaths } from '@/stores/diagram/mindMapCollapse'
import {
  type MindMapSlide,
  type MindMapSlideTraversalMode,
  buildMindMapSlides,
} from '@/utils/mindMapSlides'

export const MIND_MAP_SLIDE_AUTOPLAY_MS = 4500
export { MIND_MAP_SLIDE_TRANSITION_MS }
const AUTOPLAY_PROGRESS_TICK_MS = 50

interface SlidePreShowSnapshot {
  collapsedPaths: string[]
}

export function useMindMapSlidePresentation(options: {
  active: () => boolean
  onExitPresentation: () => void
  onExitSlides: () => void
}) {
  const diagramStore = useDiagramStore()
  const { mindMapRecalcTrigger } = storeToRefs(diagramStore)

  const slides = ref<MindMapSlide[]>([])
  const slideIndex = ref(0)
  const autoPlay = ref(false)
  const transitioning = ref(false)
  const traversalMode = ref<MindMapSlideTraversalMode>('firstLevel')
  const autoPlayProgress = ref(0)

  let autoPlayTimer: ReturnType<typeof setTimeout> | null = null
  let autoPlayProgressTimer: ReturnType<typeof setInterval> | null = null
  let preShowSnapshot: SlidePreShowSnapshot | null = null
  let disposed = false
  let startToken = 0

  const slideCount = computed(() => slides.value.length)
  const currentSlide = computed(() => slides.value[slideIndex.value] ?? null)
  const slideFocusNodeId = computed(() => {
    if (!options.active()) return null
    return currentSlide.value?.branchNodeId ?? null
  })
  const slideDimFocusNodeIds = computed(() => {
    if (!options.active()) return null
    const slide = currentSlide.value
    if (!slide || slide.kind === 'overview') return null
    return new Set(slide.focusNodeIds)
  })
  const slideBreadcrumb = computed(() => currentSlide.value?.breadcrumb ?? [])
  const isOverviewSlide = computed(() => currentSlide.value?.kind === 'overview')
  const canGoPrev = computed(() => slideIndex.value > 0)
  const canGoNext = computed(() => slideIndex.value < slides.value.length - 1)

  function clearAutoPlayTimer(): void {
    if (autoPlayTimer !== null) {
      clearTimeout(autoPlayTimer)
      autoPlayTimer = null
    }
  }

  function clearAutoPlayProgressTimer(): void {
    if (autoPlayProgressTimer !== null) {
      clearInterval(autoPlayProgressTimer)
      autoPlayProgressTimer = null
    }
  }

  function resetAutoPlayProgress(): void {
    autoPlayProgress.value = 0
  }

  function startAutoPlayProgress(): void {
    clearAutoPlayProgressTimer()
    resetAutoPlayProgress()
    if (!autoPlay.value || transitioning.value) return
    autoPlayProgressTimer = window.setInterval(() => {
      if (!autoPlay.value || transitioning.value) return
      autoPlayProgress.value = Math.min(
        1,
        autoPlayProgress.value + AUTOPLAY_PROGRESS_TICK_MS / MIND_MAP_SLIDE_AUTOPLAY_MS
      )
    }, AUTOPLAY_PROGRESS_TICK_MS)
  }

  function rebuildSlides(): void {
    const data = diagramStore.data
    if (!data) {
      slides.value = []
      return
    }
    slides.value = buildMindMapSlides(
      data.nodes ?? [],
      data.connections ?? [],
      (id) => diagramStore.getMindMapDescendantIds(id),
      traversalMode.value
    )
    slideIndex.value = 0
  }

  function emitFitSlide(slide: MindMapSlide): void {
    if (slide.branchNodeId) {
      diagramStore.expandMindMapPathToNode(slide.branchNodeId)
    }
    void nextTick(() => {
      emitMindMapSlideViewportFit(slide)
    })
  }

  function finishTransition(): void {
    transitioning.value = false
    if (autoPlay.value && options.active()) {
      scheduleAutoPlayTick()
      startAutoPlayProgress()
    }
  }

  function goToSlide(index: number, opts?: { force?: boolean }): void {
    if (!slides.value.length) return
    const next = Math.max(0, Math.min(slides.value.length - 1, index))
    if (next === slideIndex.value && !opts?.force && !transitioning.value) {
      return
    }
    slideIndex.value = next
    const slide = slides.value[next]
    if (!slide) return

    clearAutoPlayTimer()
    clearAutoPlayProgressTimer()
    resetAutoPlayProgress()
    transitioning.value = true
    emitFitSlide(slide)
    window.setTimeout(finishTransition, MIND_MAP_SLIDE_TRANSITION_MS + 80)
  }

  function advanceAutoPlaySlide(): void {
    if (!slides.value.length) return
    const last = slides.value.length - 1
    if (slideIndex.value >= last) {
      goToSlide(0, { force: true })
      return
    }
    goToSlide(slideIndex.value + 1)
  }

  function nextSlide(): void {
    if (!slides.value.length) return
    if (transitioning.value) return
    if (slideIndex.value >= slides.value.length - 1) {
      if (autoPlay.value) {
        goToSlide(0, { force: true })
      }
      return
    }
    goToSlide(slideIndex.value + 1)
  }

  function prevSlide(): void {
    if (!slides.value.length || transitioning.value) return
    goToSlide(slideIndex.value - 1)
  }

  function firstSlide(): void {
    if (!slides.value.length || transitioning.value) return
    goToSlide(0)
  }

  function lastSlide(): void {
    if (!slides.value.length || transitioning.value) return
    goToSlide(slides.value.length - 1)
  }

  function scheduleAutoPlayTick(): void {
    clearAutoPlayTimer()
    if (!autoPlay.value || !options.active() || transitioning.value) return
    autoPlayTimer = window.setTimeout(() => {
      if (!autoPlay.value || !options.active()) return
      advanceAutoPlaySlide()
    }, MIND_MAP_SLIDE_AUTOPLAY_MS)
  }

  function toggleAutoPlay(): void {
    autoPlay.value = !autoPlay.value
    if (autoPlay.value) {
      scheduleAutoPlayTick()
      startAutoPlayProgress()
    } else {
      clearAutoPlayTimer()
      clearAutoPlayProgressTimer()
      resetAutoPlayProgress()
    }
  }

  function capturePreShowState(): void {
    const data = diagramStore.data
    preShowSnapshot = {
      collapsedPaths: data?._collapsed_paths ? [...data._collapsed_paths] : [],
    }
    eventBus.emit('view:viewport_snapshot_save', {})
  }

  function restoreSlidePreShowState(): void {
    stopSlideShow()
    transitioning.value = false

    if (!preShowSnapshot) return

    const { collapsedPaths } = preShowSnapshot
    if (diagramStore.data) {
      setMindMapCollapsedPaths(diagramStore.data as Record<string, unknown>, collapsedPaths)
      mindMapRecalcTrigger.value += 1
    }

    void nextTick(() => {
      eventBus.emit('view:viewport_snapshot_restore', {
        animate: true,
        duration: MIND_MAP_SLIDE_TRANSITION_MS,
      })
    })

    preShowSnapshot = null
  }

  function exitSlideShow(): void {
    restoreSlidePreShowState()
    options.onExitSlides()
  }

  async function startSlideShow(): Promise<void> {
    const token = startToken + 1
    startToken = token
    capturePreShowState()
    rebuildSlides()
    autoPlay.value = false
    clearAutoPlayTimer()
    clearAutoPlayProgressTimer()
    resetAutoPlayProgress()
    transitioning.value = true
    await waitForMindMapSlidePlayReady(() => diagramStore.mindMapBulkLoading)
    if (disposed || token !== startToken || !options.active()) {
      transitioning.value = false
      return
    }
    goToSlide(0, { force: true })
  }

  function stopSlideShow(): void {
    autoPlay.value = false
    clearAutoPlayTimer()
    clearAutoPlayProgressTimer()
    resetAutoPlayProgress()
  }

  function setTraversalMode(mode: MindMapSlideTraversalMode): void {
    if (traversalMode.value === mode) return
    const anchorSlideId = slides.value[slideIndex.value]?.id
    traversalMode.value = mode
    rebuildSlides()
    if (!slides.value.length) return
    const nextIndex = anchorSlideId
      ? slides.value.findIndex((slide) => slide.id === anchorSlideId)
      : -1
    goToSlide(nextIndex >= 0 ? nextIndex : 0, { force: true })
  }

  function reset(): void {
    restoreSlidePreShowState()
    slides.value = []
    slideIndex.value = 0
    transitioning.value = false
    traversalMode.value = 'firstLevel'
  }

  function isTypingInInput(): boolean {
    const active = document.activeElement as HTMLElement
    return (
      active?.tagName === 'INPUT' || active?.tagName === 'TEXTAREA' || !!active?.isContentEditable
    )
  }

  function handleSlideKeyboard(event: KeyboardEvent): void {
    if (!options.active()) return
    if (isTypingInInput()) return

    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      exitSlideShow()
      return
    }

    if (event.key === ' ' || event.key === 'ArrowRight' || event.key === 'PageDown') {
      event.preventDefault()
      event.stopPropagation()
      nextSlide()
      return
    }

    if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
      event.preventDefault()
      event.stopPropagation()
      prevSlide()
      return
    }

    if (event.key === 'Home') {
      event.preventDefault()
      event.stopPropagation()
      firstSlide()
      return
    }

    if (event.key === 'End') {
      event.preventDefault()
      event.stopPropagation()
      lastSlide()
    }
  }

  function handleCanvasPaneClick(): void {
    if (!options.active() || transitioning.value) return
    nextSlide()
  }

  function handleSlideNextRequested(): void {
    if (!options.active() || transitioning.value) return
    nextSlide()
  }

  function handleSlidePrevRequested(): void {
    if (!options.active() || transitioning.value) return
    prevSlide()
  }

  const unsubPaneClick = eventBus.on('canvas:pane_clicked', handleCanvasPaneClick)
  const unsubSlideNext = eventBus.on('canvas:slide_next_requested', handleSlideNextRequested)
  const unsubSlidePrev = eventBus.on('canvas:slide_prev_requested', handleSlidePrevRequested)

  watch(
    () => options.active(),
    (on) => {
      if (on) {
        window.addEventListener('keydown', handleSlideKeyboard, true)
      } else {
        window.removeEventListener('keydown', handleSlideKeyboard, true)
        restoreSlidePreShowState()
      }
    },
    { immediate: true }
  )

  onUnmounted(() => {
    disposed = true
    startToken += 1
    window.removeEventListener('keydown', handleSlideKeyboard, true)
    unsubPaneClick()
    unsubSlideNext()
    unsubSlidePrev()
    clearAutoPlayTimer()
    clearAutoPlayProgressTimer()
  })

  return {
    slides,
    slideIndex,
    slideCount,
    currentSlide,
    slideFocusNodeId,
    slideDimFocusNodeIds,
    slideBreadcrumb,
    isOverviewSlide,
    canGoPrev,
    canGoNext,
    autoPlay,
    autoPlayProgress,
    transitioning,
    traversalMode,
    rebuildSlides,
    goToSlide,
    nextSlide,
    prevSlide,
    firstSlide,
    lastSlide,
    toggleAutoPlay,
    setTraversalMode,
    startSlideShow,
    stopSlideShow,
    restoreSlidePreShowState,
    exitSlideShow,
    reset,
  }
}
