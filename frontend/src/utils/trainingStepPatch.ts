import type { TrainingCourseStep } from '@/types/training'

/** Write one field on the course step object the builder already shares with its parent. */
export function assignTrainingStepField<K extends keyof TrainingCourseStep>(
  step: TrainingCourseStep,
  key: K,
  value: TrainingCourseStep[K]
): void {
  step[key] = value
}
