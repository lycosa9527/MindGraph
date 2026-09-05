import { watch } from 'vue'

import { useDiagramStore } from '@/stores/diagram'
import { useTrainingStore } from '@/stores/training'
import type { TrainingTopicOption } from '@/types/training'
import { postTrainingActivity } from '@/utils/trainingApi'

import { chipTopicOverride } from './applyTrainingSnapshot'
import { applyTrainingTopicToDiagram } from './trainingTopicApply'

export function useTrainingCanvasGenerate(
  handleAIGenerate: (options?: { topicOverride?: string }) => Promise<void> | void
): void {
  const training = useTrainingStore()
  const diagramStore = useDiagramStore()
  let chipInFlight = false

  watch(
    () => training.pendingJump,
    (option) => {
      if (!option) return
      applyTrainingTopicToDiagram(diagramStore, option)
      training.setPendingJump(null)
    }
  )

  watch(
    () => training.pendingChip,
    (option) => {
      if (!option || chipInFlight) return
      void runChipGenerate(option)
    }
  )

  async function runChipGenerate(option: TrainingTopicOption): Promise<void> {
    chipInFlight = true
    applyTrainingTopicToDiagram(diagramStore, option)
    const topic = chipTopicOverride(option)
    training.setPendingChip(null)
    const activity = {
      diagram_type: training.snapshot.diagram_type,
      option_id: option.id,
      option_label: option.label,
    }
    try {
      await postTrainingActivity({ ...activity, generate_state: 'generating' })
      await Promise.resolve(handleAIGenerate({ topicOverride: topic || undefined }))
    } finally {
      await postTrainingActivity({ ...activity, generate_state: 'done' })
      chipInFlight = false
    }
  }
}
