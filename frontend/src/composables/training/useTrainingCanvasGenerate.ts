import { watch } from 'vue'

import { useDiagramStore } from '@/stores/diagram'
import { useTrainingStore } from '@/stores/training'
import { postTrainingActivity } from '@/utils/trainingApi'

import { chipTopicOverride } from './applyTrainingSnapshot'
import { applyTrainingTopicToDiagram } from './trainingTopicApply'

export function useTrainingCanvasGenerate(
  handleAIGenerate: (options?: { topicOverride?: string }) => Promise<void> | void
): void {
  const training = useTrainingStore()
  const diagramStore = useDiagramStore()

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
      if (!option) return
      applyTrainingTopicToDiagram(diagramStore, option)
      const topic = chipTopicOverride(option)
      training.setPendingChip(null)
      void postTrainingActivity({
        diagram_type: training.snapshot.diagram_type,
        option_id: option.id,
        option_label: option.label,
        generate_state: 'generating',
      })
      void Promise.resolve(handleAIGenerate({ topicOverride: topic || undefined })).finally(() => {
        void postTrainingActivity({
          diagram_type: training.snapshot.diagram_type,
          option_id: option.id,
          option_label: option.label,
          generate_state: 'done',
        })
      })
    }
  )
}
