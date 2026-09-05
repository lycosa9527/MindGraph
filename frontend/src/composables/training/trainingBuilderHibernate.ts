import { trainingStepThumbKey } from '@/composables/training/trainingStageThumb'
import type { TrainingCourseStep } from '@/types/training'

export function isTrainingMediaStep(step: TrainingCourseStep | null | undefined): boolean {
  if (!step?.asset_url) return false
  return step.type === 'slide' || step.type === 'video'
}

export function shouldAwakeOnSelect(step: TrainingCourseStep | null | undefined): boolean {
  return !isTrainingMediaStep(step)
}

export function shouldRecaptureThumb(
  thumb: string | null | undefined,
  capturedKey: string | null | undefined,
  step: TrainingCourseStep | null | undefined,
  awake: boolean
): boolean {
  if (!awake || isTrainingMediaStep(step)) return false
  if (!thumb) return true
  return capturedKey !== trainingStepThumbKey(step)
}
