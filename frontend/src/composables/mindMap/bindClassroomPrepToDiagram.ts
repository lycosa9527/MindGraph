/**
 * Bind 思维讲堂 launch prep to the visible diagram (saved id + LLM variant).
 */
import { watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { isClassroomJobActive } from '@/composables/mindMap/mindClassroomJobApi'
import { useDiagramStore, useLLMResultsStore, useMindClassroomStore, useSavedDiagramsStore } from '@/stores'
import { resetLectureTtsCatchup } from '@/composables/mindMap/warmupLectureTts'
import { mindClassroomPrepKey } from '@/utils/mindClassroomPrepSlot'
import {
  collectLiveNodeIds,
  preparedLectureFitsLive,
  remapPreparedStepsToLive,
} from '@/utils/mindClassroomRemoteSteps'

export function bindClassroomPrepToDiagram(options: {
  awaitJobReady: (jobId: string, generation: number) => void
  teardownLecture: (next: { restoreViewport?: boolean; preservePrepared?: boolean }) => void
}): void {
  const classroomStore = useMindClassroomStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const llmResultsStore = useLLMResultsStore()
  const diagramStore = useDiagramStore()
  watch(
    () => [savedDiagramsStore.activeDiagramId, llmResultsStore.selectedModel] as const,
    ([nextId], previous) => {
      const prevId = previous?.[0]
      if (prevId != null && !nextId) {
        classroomStore.bumpUnsavedPrepEpoch()
      }
      const nextKey = mindClassroomPrepKey(
        nextId,
        llmResultsStore.selectedModel,
        classroomStore.unsavedPrepEpoch
      )
      const wasLecturing = classroomStore.isLecturing
      const switched = classroomStore.activatePrepKey(nextKey)
      if (switched) {
        resetLectureTtsCatchup()
      }
      if (wasLecturing) {
        options.teardownLecture({ restoreViewport: false, preservePrepared: true })
      } else if (switched) {
        classroomStore.bumpQueueGeneration()
      }
      if (prevId != null && nextId !== prevId) {
        classroomStore.closeModal()
      }
      if (!switched) return
      const liveNodes = diagramStore.data?.nodes ?? []
      if (classroomStore.preparedSteps.length) {
        const remapped = remapPreparedStepsToLive(classroomStore.preparedSteps, liveNodes)
        if (
          remapped.length &&
          preparedLectureFitsLive(
            classroomStore.preparedSteps,
            liveNodes,
            classroomStore.specNodeIds
          )
        ) {
          classroomStore.setPreparedSteps(remapped, [...collectLiveNodeIds(liveNodes)])
          return
        }
        classroomStore.setPreparedSteps([], [])
      }
      if (classroomStore.jobId && isClassroomJobActive(classroomStore.jobStatus)) {
        options.awaitJobReady(classroomStore.jobId, classroomStore.queueGeneration)
        return
      }
      if (nextId) eventBus.emit('classroom:restore_prepared_requested', {})
    },
    { immediate: true }
  )
}
