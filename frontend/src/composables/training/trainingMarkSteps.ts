import type { TrainingCourseStep, TrainingSnapshot, TrainingStepOverlay } from '@/types/training'

import { interactReadCursor, playOrderIds, readPlayIndex, savedReadOrder } from './trainingInteract'

export const TRAINING_MARK_STEPS_MIN = 1
export const TRAINING_MARK_STEPS_MAX = 8

export function overlayMarkStep(overlay: TrainingStepOverlay): number {
  const raw = overlay.step
  if (typeof raw !== 'number' || !Number.isFinite(raw)) return TRAINING_MARK_STEPS_MIN
  return Math.min(TRAINING_MARK_STEPS_MAX, Math.max(TRAINING_MARK_STEPS_MIN, Math.round(raw)))
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
  return currentMarkStep(step)
}

export function visibleMarkOverlays(step: TrainingCourseStep, at?: number): TrainingStepOverlay[] {
  const current = at ?? currentMarkStep(step)
  const due = (step.overlays || []).filter((overlay) => overlayMarkStep(overlay) <= current)
  let latestSpot: TrainingStepOverlay | undefined
  for (const overlay of due) {
    if (overlay.kind !== 'spotlight') continue
    if (!latestSpot || overlayMarkStep(overlay) >= overlayMarkStep(latestSpot)) {
      latestSpot = overlay
    }
  }
  let latestTopics: TrainingStepOverlay | undefined
  const latestRole = new Map<string, TrainingStepOverlay>()
  for (const overlay of due) {
    if (overlay.kind === 'topics') latestTopics = overlay
    if (overlay.kind !== 'role') continue
    const id = overlay.asset_id ? 'mascot' : overlay.role || ''
    const prev = latestRole.get(id)
    if (!prev || overlayMarkStep(overlay) >= overlayMarkStep(prev)) latestRole.set(id, overlay)
  }
  return due.filter((overlay) => {
    if (overlay.kind === 'spotlight') return overlay === latestSpot
    if (overlay.kind === 'topics') return overlay === latestTopics
    if (overlay.kind === 'role') {
      const id = overlay.asset_id ? 'mascot' : overlay.role || ''
      return latestRole.get(id) === overlay
    }
    return true
  })
}

function readBeat(step: TrainingCourseStep): { length: number; at: number } {
  const ids = playOrderIds(step)
  return { length: ids.length, at: ids.length > 0 ? readPlayIndex(step, ids.length) : 0 }
}

/** Marks first, then the guided-reading list. Both finish before the filmstrip moves. */
function canLeaveBeat(step: TrainingCourseStep, delta: number): boolean {
  const beat = readBeat(step)
  if (delta > 0) {
    if (currentMarkStep(step) < markStepCount(step)) return false
    return beat.at >= beat.length - 1
  }
  if (beat.at > 0) return false
  return currentMarkStep(step) <= 1
}

export function advancePlayCursor(
  steps: TrainingCourseStep[],
  selected: number,
  delta: number
): number {
  const step = steps[selected]
  if (!step || !delta) return selected
  const beat = readBeat(step)
  if (delta > 0) {
    const markAt = currentMarkStep(step)
    if (markAt < markStepCount(step)) {
      setCurrentMarkStep(step, markAt + 1)
      return selected
    }
    if (beat.at < beat.length - 1) {
      interactReadCursor.value = beat.at + 1
      return selected
    }
    const next = Math.min(steps.length - 1, selected + 1)
    if (next !== selected) {
      interactReadCursor.value = 0
      const landed = steps[next]
      if (landed) setCurrentMarkStep(landed, 1)
    }
    return next
  }
  if (beat.at > 0) {
    interactReadCursor.value = beat.at - 1
    return selected
  }
  const markAt = currentMarkStep(step)
  if (markAt > 1) {
    setCurrentMarkStep(step, markAt - 1)
    return selected
  }
  const prev = Math.max(0, selected - 1)
  if (prev !== selected) {
    const previous = steps[prev]
    if (previous) {
      setCurrentMarkStep(previous, markStepCount(previous))
      const previousIds = savedReadOrder(previous)
      interactReadCursor.value = previousIds.length > 0 ? previousIds.length - 1 : 0
    }
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
  if (!canLeaveBeat(step, delta)) return true
  if (delta > 0) return selected < steps.length - 1
  return selected > 0
}

export function canSteerLiveSnapshot(snapshot: TrainingSnapshot, delta: number): boolean {
  const step = snapshot.step
  if (!step || !delta) return false
  if (!canLeaveBeat(step, delta)) return true
  const index = snapshot.step_index || 0
  const count = snapshot.step_count || 0
  if (delta > 0) return count > 0 && index < count - 1
  return index > 0
}
