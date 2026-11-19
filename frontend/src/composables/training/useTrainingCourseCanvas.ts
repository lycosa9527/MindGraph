/**
 * A live course canvas shows the slide's saved diagram, then plays its animation.
 * The route only names the diagram type, which would otherwise open a blank template.
 */
import { nextTick, watch } from 'vue'

import { normalizeDiagramTypeKey } from '@/composables/canvasPage/newCanvasBootstrap'
import { playGlassesReveal } from '@/composables/training/glassesSlideReveal'
import {
  isCanvasCourseStep,
  preferMindMapTreeIfRicher,
  readStepDiagramSpec,
} from '@/composables/training/trainingCanvasSpec'
import { useDiagramStore } from '@/stores/diagram'
import { useTrainingStore } from '@/stores/training'
import type { DiagramType } from '@/types'
import { cloneShowcaseDiagramSpec } from '@/utils/showcaseDiagramThumbnail'

export function useTrainingCourseCanvas(): { paint: () => boolean } {
  const training = useTrainingStore()
  const diagramStore = useDiagramStore()
  let painted = ''

  function paint(force = false): boolean {
    const snap = training.snapshot
    if (snap.state !== 'live' && snap.state !== 'paused') return false
    const step = snap.step
    if (!isCanvasCourseStep(step)) return false
    const spec = readStepDiagramSpec(step)
    const raw = normalizeDiagramTypeKey(step.diagram_type || snap.diagram_type || '')
    if (!spec || !raw) return false
    const key = `${snap.session_id ?? ''}:${snap.step_index ?? 0}:${raw}`
    if (!force && key === painted) return true
    const loaded = diagramStore.loadFromSpec(
      cloneShowcaseDiagramSpec(preferMindMapTreeIfRicher(spec)),
      raw as DiagramType,
      { emitLoaded: false }
    )
    if (!loaded) return false
    painted = key
    const reveal = step.glasses_reveal || ''
    const pace = typeof step.glasses_pace === 'number' ? step.glasses_pace : 280
    void nextTick(() => {
      const root = document.querySelector('.vue-flow')
      if (root instanceof HTMLElement) void playGlassesReveal(root, reveal, pace)
    })
    return true
  }

  watch(
    () => {
      const snap = training.snapshot
      const step = snap.step
      return `${snap.state}:${snap.session_id ?? ''}:${snap.step_index ?? 0}:${step?.diagram_type ?? ''}`
    },
    () => {
      paint(false)
    }
  )

  return { paint: () => paint(true) }
}
