/**
 * Mobile canvas route/query bootstrap (type, import, library diagram).
 */
import { type ComputedRef, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { eventBus, useDiagramSpecForSave } from '@/composables'
import { applyDiagramTypeForCanvasChrome } from '@/composables/canvasPage/diagramTypeMaps'
import {
  getDiagramDataType,
  isNewCanvasTypeQuery,
  loadBlankCanvasForType,
  resolveDiagramTypeFromQuery,
  shouldPriority3LoadDefaultTemplate,
} from '@/composables/canvasPage/newCanvasBootstrap'
import { shouldSkipLibraryReloadDuringGeneration } from '@/composables/canvasPage/skipLibraryReloadDuringGeneration'
import { unloadCanvasForLibrarySwitch } from '@/composables/canvasPage/unloadCanvasForLibrarySwitch'
import type { useDiagramAutoSave } from '@/composables/editor/useDiagramAutoSave'
import {
  diagramSpecLikelyNeedsMarkdownPipeline,
  loadDiagramMarkdownPipeline,
} from '@/composables/core/diagramMarkdownPipeline'
import type { useInlineRecommendationsCoordinator } from '@/composables/editor/useInlineRecommendationsCoordinator'
import { replayKittyPendingCanvasAction } from '@/composables/kitty/useKittyMobileHubActionBridge'
import { IMPORT_SPEC_KEY } from '@/config'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import type { LocaleCode } from '@/i18n/locales'
import type { LLMResult } from '@/stores'
import type { useAuthStore } from '@/stores/auth'
import type { useDiagramStore } from '@/stores/diagram'
import type { useFeatureFlagsStore } from '@/stores/featureFlags'
import type { useLLMResultsStore } from '@/stores/llmResults'
import type { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { useUIStore } from '@/stores/ui'
import type { DiagramType } from '@/types'
import { resolveDiagramTitleForSave } from '@/utils/diagramTitleForSave'
import {
  VALID_DIAGRAM_TYPES,
  diagramTypeKeyForType,
  diagramTypeKeyFromDiagramType,
} from '@/utils/diagramTypeKeys'
import { mindMapLibraryLoadOptions } from '@/utils/mindMapLibraryLoadOptions'
import {
  beginMindMapLoadSession,
  markMindMapLoadStage,
} from '@/utils/mindMapLoadDebug'

export interface UseMobileCanvasRouteLoaderOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
  authStore: ReturnType<typeof useAuthStore>
  uiStore: ReturnType<typeof useUIStore>
  llmResultsStore: ReturnType<typeof useLLMResultsStore>
  savedDiagramsStore: ReturnType<typeof useSavedDiagramsStore>
  featureFlagsStore: ReturnType<typeof useFeatureFlagsStore>
  inlineRecCoordinator: ReturnType<typeof useInlineRecommendationsCoordinator>
  diagramType: ComputedRef<DiagramType | null>
  currentLanguage: ComputedRef<string> | { value: string }
  promptLanguage: ComputedRef<string> | { value: string }
  translate: (key: string, fallback?: string) => string
  notifySuccess: (message: string) => void
  notifyWarning: (message: string) => void
  notifyError: (message: string) => void
  onCollabClear: () => void
  diagramAutoSave: ReturnType<typeof useDiagramAutoSave>
}

export function useMobileCanvasRouteLoader(options: UseMobileCanvasRouteLoaderOptions): {
  loadDiagramFromLibrary: (diagramId: string) => Promise<boolean>
} {
  const route = useRoute()
  const router = useRouter()
  const {
    diagramStore,
    authStore,
    uiStore,
    llmResultsStore,
    savedDiagramsStore,
    featureFlagsStore,
    inlineRecCoordinator,
    diagramType,
    currentLanguage,
    promptLanguage,
    translate,
    notifySuccess,
    notifyWarning,
    notifyError,
    onCollabClear,
    diagramAutoSave,
  } = options

  /** Invalidates in-flight library loads when another diagram is selected. */
  let libraryLoadGeneration = 0

  async function loadDiagramFromLibrary(diagramId: string): Promise<boolean> {
    // URL sync after first AutoComplete save: keep live canvas + in-flight LLM streams.
    if (
      shouldSkipLibraryReloadDuringGeneration(
        llmResultsStore.isGenerating,
        diagramId,
        savedDiagramsStore.activeDiagramId
      )
    ) {
      return true
    }

    const loadGen = ++libraryLoadGeneration

    if (diagramAutoSave.isDirty.value) {
      await diagramAutoSave.flush()
    }
    if (loadGen !== libraryLoadGeneration) {
      return false
    }
    diagramAutoSave.cancelTimer()
    diagramAutoSave.setSuppressFromLibrary()

    beginMindMapLoadSession('library-mobile')
    markMindMapLoadStage('library:fetch:start', { diagramId })
    const listed = savedDiagramsStore.diagrams.find((d) => d.id === diagramId)
    unloadCanvasForLibrarySwitch(listed?.diagram_type)
    const result = await savedDiagramsStore.getDiagram(diagramId)
    if (loadGen !== libraryLoadGeneration) {
      return false
    }
    markMindMapLoadStage('library:fetch:done', { ok: result.ok })
    if (!result.ok) {
      notifyError(translate('canvas.library.diagramNotFound'))
      const nextQuery = { ...route.query }
      delete nextQuery.diagramId
      delete nextQuery.diagram_id
      await router.replace({ path: route.path, query: nextQuery })
      return false
    }
    const diagram = result.diagram
    applyDiagramTypeForCanvasChrome(diagramStore.setDiagramType, diagram.diagram_type)
    savedDiagramsStore.setActiveDiagram(diagramId)

    const spec = diagram.spec as Record<string, unknown>
    llmResultsStore.clearCache()

    if (diagramSpecLikelyNeedsMarkdownPipeline(spec)) {
      await loadDiagramMarkdownPipeline({ bumpLayout: false })
    }
    if (loadGen !== libraryLoadGeneration) {
      return false
    }
    const loadOpts = mindMapLibraryLoadOptions(diagram.diagram_type, spec)
    const loaded = diagramStore.loadFromSpec(
      spec,
      diagram.diagram_type as DiagramType,
      loadOpts
    )
    if (loaded) {
      if (diagram.title) {
        diagramStore.initTitle(diagram.title)
      }
      eventBus.emit('diagram:loaded_from_library', {
        diagramId,
        diagramType: diagram.diagram_type,
      })
      const key = diagramTypeKeyFromDiagramType(diagram.diagram_type)
      if (key) uiStore.setSelectedChartType(key)
      return true
    }
    notifyError(translate('canvas.library.diagramNotFound'))
    return false
  }

  onMounted(async () => {
    onCollabClear()
    await ensureFontsForLanguageCode(uiStore.promptLanguage)
    inlineRecCoordinator.setup()
    await nextTick()
    replayKittyPendingCanvasAction()
    await featureFlagsStore.fetchFlags()
    await savedDiagramsStore.fetchDiagrams()

    const diagramIdRaw = route.query.diagramId ?? route.query.diagram_id
    const diagramId = typeof diagramIdRaw === 'string' ? diagramIdRaw : undefined
    if (diagramId) {
      await loadDiagramFromLibrary(diagramId)
      return
    }

    const importFlag = route.query.import
    if (importFlag === '1') {
      const importJson = sessionStorage.getItem(IMPORT_SPEC_KEY)
      if (importJson) {
        try {
          const spec = JSON.parse(importJson) as Record<string, unknown>
          sessionStorage.removeItem(IMPORT_SPEC_KEY)
          const loadedType = (spec.type as DiagramType) || null
          if (!loadedType || !VALID_DIAGRAM_TYPES.includes(loadedType)) {
            notifyError(translate('notification.importUnsupportedType'))
          } else {
            const llmResults = spec.llm_results as
              | { results?: Record<string, unknown>; selectedModel?: string }
              | undefined
            let specForLoad = spec
            if (llmResults?.results && typeof llmResults.results === 'object') {
              llmResultsStore.restoreFromSaved(
                llmResults as { results?: Record<string, LLMResult>; selectedModel?: string },
                loadedType
              )
              specForLoad = { ...spec }
              delete (specForLoad as Record<string, unknown>).llm_results
            } else {
              llmResultsStore.clearCache()
            }
            if (diagramSpecLikelyNeedsMarkdownPipeline(specForLoad)) {
              await loadDiagramMarkdownPipeline({ bumpLayout: false })
            }
            const loaded = diagramStore.loadFromSpec(
              specForLoad,
              loadedType,
              mindMapLibraryLoadOptions(loadedType, specForLoad)
            )
            if (loaded) {
              const key = diagramTypeKeyForType(loadedType)
              if (key) {
                uiStore.setSelectedChartType(key)
              }
              await router.replace({ path: '/m/canvas' })

              const importTitle = resolveDiagramTitleForSave(
                diagramStore.effectiveTitle,
                loadedType,
                currentLanguage.value as LocaleCode
              )
              diagramStore.initTitle(importTitle)
              const getDiagramSpec = useDiagramSpecForSave()
              const specToSave = getDiagramSpec()
              if (specToSave && authStore.isAuthenticated) {
                const saveResult = await savedDiagramsStore.manualSaveDiagram(
                  importTitle,
                  loadedType,
                  specToSave,
                  promptLanguage.value,
                  null
                )
                if (saveResult.success) {
                  notifySuccess(translate('notification.importSuccess'))
                } else if (saveResult.needsSlotClear) {
                  eventBus.emit('canvas:show_slot_full_modal', {})
                } else if (!saveResult.success) {
                  notifyWarning(saveResult.error || translate('notification.importSavePartial'))
                }
              }
              return
            }
            notifyError(translate('notification.importLoadFailed'))
          }
        } catch (error) {
          console.error('Import load failed:', error)
          notifyError(translate('notification.importInvalidData'))
        }
      } else {
        notifyError(translate('canvas.import.invalidFile'))
        const restQuery = { ...route.query }
        delete restQuery.import
        await router.replace({ path: route.path, query: restQuery })
      }
    }

    const typeFromUrl = resolveDiagramTypeFromQuery(route.query)
    if (typeFromUrl && isNewCanvasTypeQuery(route.query)) {
      loadBlankCanvasForType({
        diagramType: typeFromUrl,
        setDiagramType: (type) => diagramStore.setDiagramType(type),
        clearActiveDiagram: () => savedDiagramsStore.clearActiveDiagram(),
        loadDefaultTemplate: (type) => diagramStore.loadDefaultTemplate(type),
        setSelectedChartType: (name) => uiStore.setSelectedChartType(name),
        hasDiagramData: Boolean(diagramStore.data),
      })
      return
    }

    // No ?type=: keep landing-generated Pinia when data.type matches; else blank.
    if (diagramType.value) {
      diagramStore.setDiagramType(diagramType.value)
      if (!savedDiagramsStore.activeDiagramId) {
        savedDiagramsStore.clearActiveDiagram()
      }
      if (
        shouldPriority3LoadDefaultTemplate({
          hasActiveDiagramId: Boolean(savedDiagramsStore.activeDiagramId),
          hasDiagramData: Boolean(diagramStore.data),
          selectedDiagramType: diagramType.value,
          dataDiagramType: getDiagramDataType(diagramStore.data),
        })
      ) {
        diagramStore.loadDefaultTemplate(diagramType.value)
      }
    }
  })

  return { loadDiagramFromLibrary }
}
