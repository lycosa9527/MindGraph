import { computed, type ComputedRef } from 'vue'

import { useTrainingStore } from '@/stores/training'
import type { TrainingCourseStep, TrainingTopicOption } from '@/types/training'

export const TRAINING_TOPIC_OPTION_MAX = 20
export const TRAINING_TOPICS_DRAG = 'application/x-mg-training-topics'

export function setTrainingTopicsDragLive(next: boolean): void {
  useTrainingStore().setTopicsDragLive(next)
}

export function useTrainingTopicsDragLive(): ComputedRef<boolean> {
  const training = useTrainingStore()
  return computed(() => training.topicsDragLive)
}

export function isTrainingTopicsDrag(transfer: DataTransfer | null): boolean {
  if (!transfer) return false
  const types = Array.from(transfer.types)
  return types.includes(TRAINING_TOPICS_DRAG) || types.includes('text/plain')
}

export function isTrainingTopicsDrop(transfer: DataTransfer | null): boolean {
  if (!transfer) return false
  if (transfer.getData(TRAINING_TOPICS_DRAG) === '1') return true
  return transfer.getData('text/plain') === 'topics'
}

export function stepUsesDualTopics(step: TrainingCourseStep | null | undefined): boolean {
  const type = step?.diagram_type || ''
  return type === 'double_bubble_map'
}

export function topicOptionDraft(index: number, dual: boolean): TrainingTopicOption {
  const id = `opt-${Date.now().toString(36)}-${index}`
  if (dual) {
    return { id, label: '', item_a: '', item_b: '' }
  }
  return { id, label: '', prompt: '' }
}

export function topicOptionLabel(option: TrainingTopicOption, dual: boolean): string {
  if (dual) {
    const left = (option.item_a || '').trim()
    const right = (option.item_b || '').trim()
    if (left && right) return `${left} vs ${right}`
    return left || right
  }
  return (option.prompt || option.label || '').trim()
}

export function normalizeTopicOptions(
  options: TrainingTopicOption[],
  dual: boolean
): TrainingTopicOption[] {
  const next: TrainingTopicOption[] = []
  for (const option of options) {
    const label = topicOptionLabel(option, dual)
    if (!label) continue
    if (dual && (!(option.item_a || '').trim() || !(option.item_b || '').trim())) {
      continue
    }
    next.push({
      id: option.id || `opt-${next.length}`,
      label,
      item_a: dual ? (option.item_a || '').trim() : null,
      item_b: dual ? (option.item_b || '').trim() : null,
      prompt: dual ? null : label,
    })
    if (next.length >= TRAINING_TOPIC_OPTION_MAX) break
  }
  return next
}

export function draftsFromStep(step: TrainingCourseStep): TrainingTopicOption[] {
  const dual = stepUsesDualTopics(step)
  const rows = (step.topic_options || []).map((option, index) => {
    if (dual) {
      return {
        id: option.id || `opt-${index}`,
        label: option.label || '',
        item_a: option.item_a || '',
        item_b: option.item_b || '',
      }
    }
    return {
      id: option.id || `opt-${index}`,
      label: option.label || '',
      prompt: option.prompt || option.label || '',
    }
  })
  return rows.length ? rows : [topicOptionDraft(0, dual)]
}
