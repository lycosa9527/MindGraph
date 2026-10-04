/**
 * Keeps gallery, sidebar, and canvas Back inside the slide deck.
 * A click inside the shell arms the router; the guard writes the page onto the slide.
 */
import type { InjectionKey } from 'vue'
import { inject, provide } from 'vue'

import { applyPageKey } from '@/composables/training/trainingBuilderSteps'
import { TRAINING_PAGES, type TrainingPageKey } from '@/config/trainingPages'
import type { TrainingCourseStep } from '@/types/training'

export interface TrainingDeckTarget {
  pageKey: TrainingPageKey
  diagramType: string | null
}

export interface TrainingDeckNav {
  openPage: (pageKey: TrainingPageKey, diagramType?: string | null) => void
  openDiagram: (diagramType: string) => void
  backFromCanvas: () => void
}

const DECK_NAV: InjectionKey<TrainingDeckNav> = Symbol('trainingDeckNav')

type DeckSink = (target: TrainingDeckTarget) => void

const sinks: DeckSink[] = []
let armed = false

export function trainingPageFromLocation(
  path: string,
  typeQuery: unknown
): TrainingDeckTarget | null {
  const page = TRAINING_PAGES.find((item) => item.path === path || item.mobilePath === path)
  if (!page) return null
  if (page.key !== 'canvas') return { pageKey: page.key, diagramType: null }
  const raw = typeof typeQuery === 'string' ? typeQuery.trim() : ''
  return { pageKey: 'canvas', diagramType: raw || null }
}

export function pushTrainingDeckSink(sink: DeckSink): () => void {
  sinks.push(sink)
  return () => {
    const index = sinks.lastIndexOf(sink)
    if (index >= 0) sinks.splice(index, 1)
  }
}

export function armTrainingDeckNavigation(): void {
  if (sinks.length === 0) return
  armed = true
  // Router guards run in a microtask. A timeout clears the arm only when
  // the click never starts a navigation, so the real app is not swallowed.
  window.setTimeout(() => {
    armed = false
  }, 0)
}

export function consumeTrainingDeckNavigation(path: string, typeQuery: unknown): boolean {
  if (!armed || sinks.length === 0) return false
  armed = false
  const target = trainingPageFromLocation(path, typeQuery)
  const sink = sinks[sinks.length - 1]
  if (target && sink) sink(target)
  return true
}

export function applyDeckPage(
  step: TrainingCourseStep,
  pageKey: TrainingPageKey,
  diagramType: string | null
): void {
  applyPageKey(step, pageKey)
  if (pageKey !== 'canvas' || !diagramType) return
  step.diagram_type = diagramType === 'mind_map' ? 'mindmap' : diagramType
}

export function provideTrainingDeckNav(nav: TrainingDeckNav): void {
  provide(DECK_NAV, nav)
}

export function useTrainingDeckNav(): TrainingDeckNav | null {
  return inject(DECK_NAV, null)
}
