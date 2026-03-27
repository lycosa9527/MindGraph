import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramAutoSave } from '@/composables/editor/useDiagramAutoSave'
import { useSnapshotHistory } from '@/composables/editor/useSnapshotHistory'
import {
  type LLMResult,
  useDiagramStore,
  useLLMResultsStore,
  useUIStore,
} from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'

import { diagramTypeMap } from './diagramTypeMaps'

type SnapshotHistoryApi = ReturnType<typeof useSnapshotHistory>

export function useCanvasPageLibrarySnapshots(options: {
  diagramAutoSave: ReturnType<typeof useDiagramAutoSave>
  snapshotHistory: SnapshotHistoryApi
}): {
  loadDiagramFromLibrary: (diagramId: string) => Promise<void>
  handleSnapshotRecall: (versionNumber: number) => Promise<void>
  handleSnapshotDelete: (versionNumber: number) => Promise<void>
} {
  const { diagramAutoSave, snapshotHistory } = options
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const llmResultsStore = useLLMResultsStore()
  const uiStore = useUIStore()
  const notify = useNotifications()
  const { t } = useLanguage()

  async function loadDiagramFromLibrary(diagramId: string): Promise<void> {
    diagramStore.resetSessionEditCount()
    const diagram = await savedDiagramsStore.getDiagram(diagramId)
    if (diagram) {
      savedDiagramsStore.setActiveDiagram(diagramId)
      diagramStore.clearHistory()

      const spec = diagram.spec as Record<string, unknown>
      const llmResults = spec?.llm_results as
        | { results?: Record<string, unknown>; selectedModel?: string }
        | undefined
      let specForLoad = spec
      if (llmResults?.results && typeof llmResults.results === 'object') {
        llmResultsStore.restoreFromSaved(
          llmResults as { results?: Record<string, LLMResult>; selectedModel?: string },
          diagram.diagram_type
        )
        specForLoad = { ...spec }
        delete (specForLoad as Record<string, unknown>).llm_results
      } else {
        llmResultsStore.clearCache()
      }

      eventBus.emit('diagram:loaded_from_library', {
        diagramId,
        diagramType: diagram.diagram_type,
      })
      const loaded = diagramStore.loadFromSpec(specForLoad, diagram.diagram_type as DiagramType)

      if (loaded) {
        uiStore.setSelectedChartType(
          Object.entries(diagramTypeMap).find(([_, v]) => v === diagram.diagram_type)?.[0] ||
            diagram.diagram_type
        )
      }
      snapshotHistory.setActiveVersion(null)
      await snapshotHistory.loadSnapshots(diagramId)
    }
  }

  async function handleSnapshotRecall(versionNumber: number): Promise<void> {
    const diagramId = savedDiagramsStore.activeDiagramId
    const diagramType = diagramStore.type
    if (!diagramId || !diagramType) return

    await diagramAutoSave.flush()

    const spec = await snapshotHistory.recallSnapshot(diagramId, versionNumber)
    if (!spec) {
      notify.error(t('canvas.topBar.snapshotRecallFailed'))
      return
    }

    diagramStore.pushHistory(t('canvas.topBar.snapshotRecallHistory', { n: versionNumber }))
    llmResultsStore.clearCache()
    eventBus.emit('diagram:loaded_from_library', { diagramId, diagramType })
    diagramStore.loadFromSpec(spec, diagramType)
    snapshotHistory.setActiveVersion(versionNumber)
  }

  async function handleSnapshotDelete(versionNumber: number): Promise<void> {
    const diagramId = savedDiagramsStore.activeDiagramId
    if (!diagramId) return

    const deleted = await snapshotHistory.deleteSnapshot(diagramId, versionNumber)
    if (deleted) {
      notify.success(t('canvas.topBar.snapshotDeleted', { n: versionNumber }))
    } else {
      notify.error(t('canvas.topBar.snapshotDeleteFailed'))
    }
  }

  return {
    loadDiagramFromLibrary,
    handleSnapshotRecall,
    handleSnapshotDelete,
  }
}
