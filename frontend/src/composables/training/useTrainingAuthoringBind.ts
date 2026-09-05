import { onMounted, onUnmounted } from 'vue'

import { applyDiagramCardStep } from '@/composables/training/trainingBuilderSteps'
import { isTrainingFocusKey, shouldBlockTrainingAuthoringClick } from '@/config/trainingUiTargets'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'

export function useTrainingAuthoringBind(): void {
  const builder = useTrainingBuilderStore()

  function onClick(event: MouseEvent): void {
    const step = builder.current
    if (!step || builder.isSystem) return
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
