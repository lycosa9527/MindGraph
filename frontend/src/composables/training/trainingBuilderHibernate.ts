import { trainingStepPageKey } from '@/composables/training/trainingStageThumb'
import type { TrainingCourseStep } from '@/types/training'

export function isTrainingMediaStep(step: TrainingCourseStep | null | undefined): boolean {
  if (!step?.asset_url) return false
  return step.type === 'slide' || step.type === 'video'
}

export function shouldAwakeOnSelect(
  thumb: string | null | undefined,
  step: TrainingCourseStep | null | undefined
): boolean {
  if (isTrainingMediaStep(step)) return false
  return !thumb
}

export function shouldRecaptureThumb(
  thumb: string | null | undefined,
  capturedPageKey: string | null | undefined,
  step: TrainingCourseStep | null | undefined,
  awake: boolean
): boolean {
  if (!awake || isTrainingMediaStep(step)) return false
  if (!thumb) return true
  return capturedPageKey !== trainingStepPageKey(step)
}
