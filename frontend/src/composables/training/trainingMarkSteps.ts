import type { TrainingCourseStep, TrainingStepOverlay } from '@/types/training'

export const TRAINING_MARK_STEPS_MIN = 1
export const TRAINING_MARK_STEPS_MAX = 8

export function overlayMarkStep(overlay: TrainingStepOverlay): number {
  const raw = overlay.step
  if (typeof raw !== 'number' || !Number.isFinite(raw)) return 2
  return Math.min(TRAINING_MARK_STEPS_MAX, Math.max(2, Math.round(raw)))
}

export function markStepCount(step: TrainingCourseStep): number {
  let highest = TRAINING_MARK_STEPS_MIN
  const stored = step.mark_steps
  if (typeof stored === 'number' && Number.isFinite(stored)) {
    highest = Math.round(stored)
  }
  for (const overlay of step.overlays || []) {
    highest = Math.max(highest, overlayMarkStep(overlay))
  }
  return Math.min(TRAINING_MARK_STEPS_MAX, Math.max(TRAINING_MARK_STEPS_MIN, highest))
}

export function currentMarkStep(step: TrainingCourseStep): number {
  const raw = step.mark_step
  const count = markStepCount(step)
  if (typeof raw !== 'number' || !Number.isFinite(raw)) return 1
  return Math.min(count, Math.max(TRAINING_MARK_STEPS_MIN, Math.round(raw)))
}

export function setCurrentMarkStep(step: TrainingCourseStep, next: number): void {
  const count = markStepCount(step)
  step.mark_step = Math.min(count, Math.max(TRAINING_MARK_STEPS_MIN, Math.round(next)))
}

export function addMarkStep(step: TrainingCourseStep): void {
  const count = markStepCount(step)
  if (count >= TRAINING_MARK_STEPS_MAX) return
  step.mark_steps = count + 1
  step.mark_step = count + 1
}

export function removeMarkStep(step: TrainingCourseStep): void {
  const current = currentMarkStep(step)
  if (current <= TRAINING_MARK_STEPS_MIN) return
  const count = markStepCount(step)
  const nextOverlays: TrainingStepOverlay[] = []
  for (const overlay of step.overlays || []) {
    const owned = overlayMarkStep(overlay)
    if (owned === current) continue
    if (owned > current) overlay.step = owned - 1
    nextOverlays.push(overlay)
  }
  step.overlays = nextOverlays
  step.mark_steps = Math.max(TRAINING_MARK_STEPS_MIN, count - 1)
  step.mark_step = Math.min(current, step.mark_steps)
}

export function allocateOverlayStep(step: TrainingCourseStep): number {
  const current = currentMarkStep(step)
  const count = markStepCount(step)
  if (current <= 1) {
    addMarkStep(step)
    return currentMarkStep(step)
  }
  const occupied = (step.overlays || []).some((overlay) => overlayMarkStep(overlay) === current)
  if (occupied && current === count && count < TRAINING_MARK_STEPS_MAX) {
    addMarkStep(step)
    return currentMarkStep(step)
  }
  return current
}

export function visibleMarkOverlays(
  step: TrainingCourseStep,
  at?: number
): TrainingStepOverlay[] {
  const current = at ?? currentMarkStep(step)
  if (current <= 1) return []
  const due = (step.overlays || []).filter((overlay) => overlayMarkStep(overlay) <= current)
  let latestSpot: TrainingStepOverlay | undefined
  for (const overlay of due) {
    if (overlay.kind !== 'spotlight') continue
    if (!latestSpot || overlayMarkStep(overlay) >= overlayMarkStep(latestSpot)) {
      latestSpot = overlay
    }
  }
  let latestTopics: TrainingStepOverlay | undefined
  for (const overlay of due) {
    if (overlay.kind !== 'topics') continue
    latestTopics = overlay
  }
  return due.filter((overlay) => {
    if (overlay.kind === 'spotlight') return overlay === latestSpot
    if (overlay.kind === 'topics') return overlay === latestTopics
    return true
  })
}

export function advancePlayCursor(
  steps: TrainingCourseStep[],
  selected: number,
  delta: number
): number {
  const step = steps[selected]
  if (!step || !delta) return selected
  if (delta > 0) {
    const count = markStepCount(step)
    const at = currentMarkStep(step)
    if (at < count) {
      setCurrentMarkStep(step, at + 1)
      return selected
    }
    const next = Math.min(steps.length - 1, selected + 1)
    if (next !== selected) setCurrentMarkStep(steps[next], 1)
    return next
  }
  const at = currentMarkStep(step)
  if (at > 1) {
    setCurrentMarkStep(step, at - 1)
    return selected
  }
  const prev = Math.max(0, selected - 1)
  if (prev !== selected) {
    setCurrentMarkStep(steps[prev], markStepCount(steps[prev]))
  }
  return prev
}

export function canAdvancePlayCursor(
  steps: TrainingCourseStep[],
  selected: number,
  delta: number
): boolean {
  const step = steps[selected]
  if (!step || !delta) return false
  if (delta > 0) {
    return currentMarkStep(step) < markStepCount(step) || selected < steps.length - 1
  }
  return currentMarkStep(step) > 1 || selected > 0
}
