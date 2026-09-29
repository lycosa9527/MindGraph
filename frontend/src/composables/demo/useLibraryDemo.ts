/**
 * Shared library-demo deck: picker open state, slide clock, and playback.
 */
import { ref } from 'vue'

import type { DemoCaptionDraft } from '@/composables/demo/demoCaptionDefaults'
import { DEMO_TEMPLATE_MS, type DemoPhase, demoPhaseAfter } from '@/composables/demo/demoPlayback'

export interface DemoDeckSlide {
  id: string
  title: string
  diagramType: string
  thumbnail: string | null
  caption: DemoCaptionDraft
}

const pickerOpen = ref(false)
const stageOpen = ref(false)
const deck = ref<DemoDeckSlide[]>([])
const slideIndex = ref(0)
const paused = ref(false)
const phase = ref<DemoPhase>('template')

let timer = 0
let phaseBudget = DEMO_TEMPLATE_MS
let phaseStartedAt = 0
let ownsFullscreen = false

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function clearTimer(): void {
  window.clearTimeout(timer)
  timer = 0
}

function claimFullscreen(): void {
  if (typeof document === 'undefined' || document.fullscreenElement) return
  const root = document.documentElement
  if (!root.requestFullscreen) return
  ownsFullscreen = true
  void root.requestFullscreen().catch(() => {
    ownsFullscreen = false
  })
}

function releaseFullscreen(): void {
  if (!ownsFullscreen || typeof document === 'undefined') return
  ownsFullscreen = false
  if (document.fullscreenElement) {
    void document.exitFullscreen().catch(() => undefined)
  }
}

function remainingMs(): number {
  if (!phaseStartedAt) return phaseBudget
  return Math.max(0, phaseBudget - (Date.now() - phaseStartedAt))
}

function armTimer(): void {
  clearTimer()
  if (!stageOpen.value || paused.value || deck.value.length === 0) return
  if (phase.value !== 'template') return
  phaseStartedAt = Date.now()
  timer = window.setTimeout(onPhaseElapsed, phaseBudget)
}

function onPhaseElapsed(): void {
  if (phase.value !== 'template') return
  phase.value = demoPhaseAfter(DEMO_TEMPLATE_MS, false)
  phaseBudget = 0
  phaseStartedAt = 0
  clearTimer()
}

function goTo(next: number, keepPause: boolean): void {
  const length = deck.value.length
  if (length === 0) return
  slideIndex.value = ((next % length) + length) % length
  const reduce = prefersReducedMotion()
  phase.value = demoPhaseAfter(0, reduce)
  phaseBudget = DEMO_TEMPLATE_MS
  phaseStartedAt = 0
  if (!keepPause) paused.value = false
  armTimer()
}

export function useLibraryDemo() {
  function openPicker(): void {
    pickerOpen.value = true
  }

  function closePicker(): void {
    pickerOpen.value = false
  }

  function startDeck(slides: DemoDeckSlide[]): void {
    if (slides.length === 0) return
    deck.value = slides
    pickerOpen.value = false
    stageOpen.value = true
    paused.value = false
    goTo(0, false)
  }

  function closeStage(): void {
    stageOpen.value = false
    phase.value = 'template'
    paused.value = false
    clearTimer()
    releaseFullscreen()
  }

  function step(delta: number): void {
    goTo(slideIndex.value + delta, paused.value)
  }

  function jumpTo(index: number): void {
    goTo(index, paused.value)
  }

  function advanceAfterTour(): void {
    if (!stageOpen.value || paused.value) return
    goTo(slideIndex.value + 1, false)
  }

  function togglePause(): void {
    if (!stageOpen.value) return
    if (paused.value) {
      paused.value = false
      armTimer()
      return
    }
    phaseBudget = remainingMs()
    paused.value = true
    clearTimer()
  }

  return {
    pickerOpen,
    stageOpen,
    deck,
    slideIndex,
    paused,
    phase,
    openPicker,
    closePicker,
    claimFullscreen,
    releaseFullscreen,
    startDeck,
    closeStage,
    step,
    jumpTo,
    togglePause,
    advanceAfterTour,
  }
}
