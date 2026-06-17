/**
 * Mind map slide presentation: overview + level-1 branches, auto-play, keyboard nav.
 */
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore } from '@/stores'
import { buildMindMapSlides, type MindMapSlide } from '@/utils/mindMapSlides'

export const MIND_MAP_SLIDE_AUTOPLAY_MS = 4500
export const MIND_MAP_SLIDE_TRANSITION_MS = 920

export function useMindMapSlidePresentation(options: {
  active: () => boolean
  onExitPresentation: () => void
}) {
  const diagramStore = useDiagramStore()

  const slides = ref<MindMapSlide[]>([])
  const slideIndex = ref(0)
  const autoPlay = ref(false)
  const transitioning = ref(false)

  let autoPlayTimer: ReturnType<typeof setTimeout> | null = null

  const slideCount = computed(() => slides.value.length)
  const currentSlide = computed(() => slides.value[slideIndex.value] ?? null)

  function clearAutoPlayTimer(): void {
    if (autoPlayTimer !== null) {
      clearTimeout(autoPlayTimer)
      autoPlayTimer = null
    }
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
      (id) => diagramStore.getMindMapDescendantIds(id)
    )
    slideIndex.value = 0
  }

  function emitFitSlide(slide: MindMapSlide): void {
    if (slide.branchNodeId) {
      diagramStore.expandMindMapPathToNode(slide.branchNodeId)
    }
    void nextTick(() => {
      eventBus.emit('view:fit_to_nodes_requested', {
        nodeIds: slide.focusNodeIds,
        animate: true,
        duration: MIND_MAP_SLIDE_TRANSITION_MS,
        padding: slide.kind === 'overview' ? 0.28 : 0.38,
        userInitiated: true,
      })
    })
  }

  function finishTransition(): void {
    transitioning.value = false
    if (autoPlay.value && options.active()) {
      scheduleAutoPlayTick()
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
    } else {
      clearAutoPlayTimer()
    }
  }

  function startSlideShow(): void {
    rebuildSlides()
    autoPlay.value = false
    clearAutoPlayTimer()
    goToSlide(0, { force: true })
  }

  function stopSlideShow(): void {
    autoPlay.value = false
    clearAutoPlayTimer()
  }

  function reset(): void {
    stopSlideShow()
    slides.value = []
    slideIndex.value = 0
    transitioning.value = false
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
      options.onExitPresentation()
      return
    }

    if (event.key === ' ' || event.key === 'ArrowRight') {
      event.preventDefault()
      event.stopPropagation()
      nextSlide()
      return
    }

    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      event.stopPropagation()
      prevSlide()
    }
  }

  watch(
    () => options.active(),
    (on) => {
      if (on) {
        window.addEventListener('keydown', handleSlideKeyboard, true)
      } else {
        window.removeEventListener('keydown', handleSlideKeyboard, true)
        stopSlideShow()
      }
    },
    { immediate: true }
  )

  onUnmounted(() => {
    window.removeEventListener('keydown', handleSlideKeyboard, true)
    clearAutoPlayTimer()
  })

  return {
    slides,
    slideIndex,
    slideCount,
    currentSlide,
    autoPlay,
    transitioning,
    rebuildSlides,
    goToSlide,
    nextSlide,
    prevSlide,
    toggleAutoPlay,
    startSlideShow,
    stopSlideShow,
    reset,
  }
}
