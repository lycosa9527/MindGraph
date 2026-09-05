import { onMounted, onUnmounted, type Ref } from 'vue'

import { applyDiagramCardStep } from '@/composables/training/trainingBuilderSteps'
import { isTrainingFocusKey, shouldBlockTrainingAuthoringClick } from '@/config/trainingUiTargets'
import type { TrainingCourseStep } from '@/types/training'

export function useTrainingAuthoringBind(current: Ref<TrainingCourseStep | null>): void {
  function onClick(event: MouseEvent): void {
    const step = current.value
    if (!step) return
    const raw = event.target
    if (!(raw instanceof Element)) return
    const el = raw.closest('[data-training-target]')
    if (!(el instanceof HTMLElement)) return
    if (el.closest('[data-training-preview]')) return
    const key = el.getAttribute('data-training-target')
    if (!isTrainingFocusKey(key) || !key) return
    if (applyDiagramCardStep(step, key)) {
      event.preventDefault()
      event.stopPropagation()
      return
    }
    step.focus_key = key
    if (!shouldBlockTrainingAuthoringClick(key)) return
    event.preventDefault()
    event.stopPropagation()
  }

  onMounted(() => {
    document.addEventListener('click', onClick, true)
  })
  onUnmounted(() => {
    document.removeEventListener('click', onClick, true)
  })
}
