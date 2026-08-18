import { type ComputedRef } from 'vue'
import { useRouter } from 'vue-router'

import {
  diagramSpecLikelyNeedsMarkdownPipeline,
  loadDiagramMarkdownPipeline,
} from '@/composables/core/diagramMarkdownPipeline'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramAutoSave } from '@/composables/editor/useDiagramAutoSave'
import { useSnapshotHistory } from '@/composables/editor/useSnapshotHistory'
import { useDiagramStore, useLLMResultsStore, useUIStore } from '@/stores'
import { splitSavedLlmResultsFromSpec } from '@/stores/llmResultsPersist'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
import { mindMapLibraryLoadOptions } from '@/utils/mindMapLibraryLoadOptions'
import {
  beginMindMapLoadSession,
  markMindMapLoadStage,
} from '@/utils/mindMapLoadDebug'

import { applyDiagramTypeForCanvasChrome, diagramTypeMap } from './diagramTypeMaps'
import { flushCanvasBeforeLibrarySwitch } from './shouldFlushBeforeLibrarySwitch'
import { shouldSkipLibraryReloadForActiveDiagram } from './skipLibraryReloadDuringGeneration'
import { unloadCanvasForLibrarySwitch } from './unloadCanvasForLibrarySwitch'

type SnapshotHistoryApi = ReturnType<typeof useSnapshotHistory>

export function useCanvasPageLibrarySnapshots(options: {
  diagramAutoSave: ReturnType<typeof useDiagramAutoSave>
  snapshotHistory: SnapshotHistoryApi
  isDiagramOwner?: ComputedRef<boolean>
}): {
  loadDiagramFromLibrary: (diagramId: string) => Promise<boolean>
  handleSnapshotRecall: (versionNumber: number) => Promise<void>
  handleSnapshotDelete: (versionNumber: number) => Promise<void>
} {
  const { diagramAutoSave, snapshotHistory, isDiagramOwner } = options
  const router = useRouter()
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const llmResultsStore = useLLMResultsStore()
  const uiStore = useUIStore()
  const notify = useNotifications()
  const { t } = useLanguage()

  /** Invalidates in-flight library loads when the user selects another diagram. */
  let libraryLoadGeneration = 0

  async function loadDiagramFromLibrary(diagramId: string): Promise<boolean> {
    // URL sync after first AutoComplete save: keep live canvas + in-flight LLM streams.
    if (shouldSkipLibraryReloadForActiveDiagram(diagramId, savedDiagramsStore.activeDiagramId)) {
      return true
    }

    const loadGen = ++libraryLoadGeneration

    // Persist the previous canvas before tearing it down — clearing data while
    // activeDiagramId still points at the old row could autosave an empty wipe.
    // flushOnLeave bypasses suppress/LLM/subgraph; fail closed unless collab
    // owns durability via live_spec (REST save is intentionally blocked).
    const flushBeforeSwitch = await flushCanvasBeforeLibrarySwitch({
      isDirty: diagramAutoSave.isDirty.value,
      isGenerating: llmResultsStore.isGenerating,
      drainPersistQueue: () => diagramAutoSave.drainPersistQueue(),
      flushOnLeave: () => diagramAutoSave.flushOnLeave(),
      collabOwnsPersist: diagramStore.collabSessionActive,
    })
    if (flushBeforeSwitch === 'failed') {
      notify.warning(t('canvas.library.saveBeforeSwitchFailed'))
      return false
    }
    if (loadGen !== libraryLoadGeneration) {
      return false
    }
    diagramAutoSave.cancelTimer()
    diagramAutoSave.setSuppressFromLibrary()
    snapshotHistory.clearSnapshots()

    beginMindMapLoadSession('library')
    markMindMapLoadStage('library:fetch:start', { diagramId })
    const listed = savedDiagramsStore.diagrams.find((d) => d.id === diagramId)
    // Unload old canvas + sync chrome in the same tick so neither previous
    // toolbar nor previous nodes can paint during the fetch await.
    unloadCanvasForLibrarySwitch(listed?.diagram_type)
    const result = await savedDiagramsStore.getDiagram(diagramId, { force: true })
    if (loadGen !== libraryLoadGeneration) {
      return false
    }
    markMindMapLoadStage('library:fetch:done', { ok: result.ok })
    if (!result.ok) {
      notify.error(t('canvas.library.diagramNotFound'))
      const nextQuery = { ...router.currentRoute.value.query }
      delete nextQuery.diagramId
      delete nextQuery.diagram_id
      await router.replace({ path: router.currentRoute.value.path, query: nextQuery })
      return false
    }
    const diagram = result.diagram
    applyDiagramTypeForCanvasChrome(diagramStore.setDiagramType, diagram.diagram_type)
    savedDiagramsStore.setActiveDiagram(diagramId)

    const spec = diagram.spec as Record<string, unknown>
    const { specForLoad, saved: llmResults } = splitSavedLlmResultsFromSpec(spec)
    if (llmResults) {
      llmResultsStore.restoreFromSaved(llmResults, diagram.diagram_type)
    } else {
      llmResultsStore.clearCache()
    }

    if (diagramSpecLikelyNeedsMarkdownPipeline(specForLoad)) {
      await loadDiagramMarkdownPipeline({ bumpLayout: false })
    }
    if (loadGen !== libraryLoadGeneration) {
      return false
    }
    const loadOpts = mindMapLibraryLoadOptions(diagram.diagram_type, specForLoad)
    const loaded = diagramStore.loadFromSpec(
      specForLoad,
      diagram.diagram_type as DiagramType,
      loadOpts
    )

    if (loaded) {
      if (diagram.title) {
        diagramStore.initTitle(diagram.title)
      }
      // Emit after Pinia replace so listeners do not read the previous diagram.
      eventBus.emit('diagram:loaded_from_library', {
        diagramId,
        diagramType: diagram.diagram_type,
      })
      uiStore.setSelectedChartType(
        Object.entries(diagramTypeMap).find(([_, v]) => v === diagram.diagram_type)?.[0] ||
          diagram.diagram_type
      )
    } else {
      notify.error(t('canvas.library.diagramNotFound'))
      return false
    }
    snapshotHistory.setActiveVersion(null)
    return true
  }

  function resolveDiagramTypeForRecall(): DiagramType | null {
    if (diagramStore.type) {
      return diagramStore.type
    }
    const fromData = diagramStore.data?.type
    if (typeof fromData === 'string' && fromData.length > 0) {
      return fromData as DiagramType
    }
    return null
  }

  async function handleSnapshotRecall(versionNumber: number): Promise<void> {
    if (diagramStore.collabSessionActive && isDiagramOwner?.value === false) return
    if (snapshotHistory.recallingVersion.value !== null) return
    const diagramId = savedDiagramsStore.activeDiagramId
    const diagramType = resolveDiagramTypeForRecall()
    if (!diagramId) {
      notify.warning(t('canvas.topBar.snapshotRecallNoDiagram'))
      return
    }
    if (!diagramType) {
      notify.warning(t('canvas.topBar.snapshotRecallNoType'))
      return
    }

    snapshotHistory.setRecallingVersion(versionNumber)
    try {
      if (diagramAutoSave.isDirty.value) {
        await diagramAutoSave.flush()
      }

      const recallResult = await snapshotHistory.recallSnapshot(diagramId, versionNumber)
      if (!recallResult.ok) {
        notify.error(recallResult.message || t('canvas.topBar.snapshotRecallFailed'))
        return
      }
      const spec = recallResult.spec

      diagramStore.pushHistory(t('canvas.topBar.snapshotRecallHistory', { n: versionNumber }))
      llmResultsStore.clearCache()
      if (diagramSpecLikelyNeedsMarkdownPipeline(spec)) {
        await loadDiagramMarkdownPipeline({ bumpLayout: false })
      }
      const loadOpts = mindMapLibraryLoadOptions(diagramType, spec)
      const recalled = diagramStore.loadFromSpec(spec, diagramType, loadOpts)
      if (recalled) {
        eventBus.emit('diagram:loaded_from_library', { diagramId, diagramType })
      }
      snapshotHistory.setActiveVersion(versionNumber)
    } finally {
      snapshotHistory.setRecallingVersion(null)
    }
  }

  async function handleSnapshotDelete(versionNumber: number): Promise<void> {
    if (diagramStore.collabSessionActive && isDiagramOwner?.value === false) return
    const diagramId = savedDiagramsStore.activeDiagramId
    if (!diagramId) return

    const deleteResult = await snapshotHistory.deleteSnapshot(diagramId, versionNumber)
    if (deleteResult.ok) {
      notify.success(t('canvas.topBar.snapshotDeleted', { n: versionNumber }))
    } else {
      notify.error(deleteResult.message || t('canvas.topBar.snapshotDeleteFailed'))
    }
  }

  return {
    loadDiagramFromLibrary,
    handleSnapshotRecall,
    handleSnapshotDelete,
  }
}
