/**
 * LLM Results Store - Pinia store for multi-LLM auto-complete results
 *
 * Migrated from old JavaScript:
 * - llm-autocomplete-manager.js
 * - llm-result-cache.js
 * - llm-progress-renderer.js
 *
 * Features:
 * - One model runs at a time; each model's last success stays selectable
 * - Older keys still load from saved diagrams
 * - First-result-wins rendering
 * - Click to switch between cached results
 * - Per-model loading/ready/error states
 */
import { computed, nextTick, ref } from 'vue'

import { defineStore } from 'pinia'

import { attachLlmExportAttribution } from '@/utils/llmExportWatermark'
import {
  isMindMapDiagramType,
  mergeMindMapPresentationExtrasIntoSpec,
} from '@/utils/mindMapLiveSpecExtras'

import { useAiContentLevelStore } from './aiContentLevel'
import { useDiagramStore } from './diagram'
import {
  isLlmResultForCurrentSession,
  shouldPaintCompletedLlmModel,
  shouldStampCanvasOntoLlmResult,
} from './llmResultsPaint'
import { clonePersistedLlmResults, resolvePersistedSelectedModel } from './llmResultsPersist'
import { useSavedDiagramsStore } from './savedDiagrams'

// Types
export type ModelState = 'idle' | 'loading' | 'ready' | 'error'

/** In-flight auto-complete phases for per-model button colors (AIModelSelector). */
export type ModelLoadPhase = 'idle' | 'sending' | 'waiting' | 'streaming' | 'ready' | 'error'

const IDLE_PHASES: Record<string, ModelLoadPhase> = {
  express: 'idle',
  qwen: 'idle',
  deepseek: 'idle',
  doubao: 'idle',
}

export interface LLMResult {
  success: boolean
  spec?: Record<string, unknown>
  diagramType?: string
  error?: string
  errorType?: string
  elapsed?: number
  timestamp: number
}

export interface LLMResultsState {
  results: Record<string, LLMResult>
  modelStates: Record<string, ModelState>
  selectedModel: string | null
  isGenerating: boolean
  sessionId: string | null
  expectedDiagramType: string | null
}

// Constants
const MODELS = ['express'] as const
/** Live canvas menu plus older keys still stored on diagrams. */
export type { CanvasLlmModel as LLMModel } from '@/config/canvasLlmMenu'

export {
  isLlmResultForCurrentSession,
  shouldPaintCompletedLlmModel,
  shouldStampCanvasOntoLlmResult,
} from './llmResultsPaint'

export const useLLMResultsStore = defineStore('llmResults', () => {
  const diagramStore = useDiagramStore()

  // State
  const results = ref<Record<string, LLMResult>>({})
  const modelStates = ref<Record<string, ModelState>>({
    express: 'idle',
    qwen: 'idle',
    deepseek: 'idle',
    doubao: 'idle',
  })
  const modelPhases = ref<Record<string, ModelLoadPhase>>({ ...IDLE_PHASES })
  const selectedModel = ref<string | null>(null)
  /** Menu choice kept across generation cache clears. selectedModel is the painted result. */
  const preferredModel = ref<string | null>(null)
  const isGenerating = ref(false)
  const sessionId = ref<string | null>(null)
  const expectedDiagramType = ref<string | null>(null)
  const totalModels = ref<number | null>(null)

  // Track abort controllers for cancellation
  const abortControllers = ref<AbortController[]>([])

  /**
   * Set true before loadFromSpec in switchToModel. Auto-save checks this: when
   * content change is from model switch, do not save (save-before-replace already
   * saved user edits; persisting the new model's result would overwrite them).
   */
  const contentChangeIsFromModelSwitch = ref(false)

  /** Canvas topic captured at auto-complete start; applied on every model switch/load. */
  const lockedTopic = ref<string | null>(null)

  /** Model painted by first-result-wins in the current generate round. */
  const paintedThisSession = ref<string | null>(null)
  /** Saved model the user opened while this run was still in flight. */
  const pinnedDuringRun = ref<string | null>(null)
  /** Models whose HTTP result was stored for the current generate round. */
  const acceptedThisRun = ref<Record<string, true>>({})
  /** Failure from the current round, kept even when a prior success stays. */
  const runErrors = ref<Record<string, { error: string; errorType?: string }>>({})

  // Getters
  const models = computed(() => MODELS)

  const hasAnyResults = computed(() => {
    return Object.values(results.value).some((r) => r.success)
  })

  const readyModels = computed(() => {
    return Object.entries(modelStates.value)
      .filter(([_, state]) => state === 'ready')
      .map(([model]) => model)
  })

  const successCount = computed(() => {
    return Object.values(results.value).filter((r) => r.success).length
  })

  /** A successful spec stays until that model is replaced or the diagram session clears. */
  function isResultValid(model: string): boolean {
    const result = results.value[model]
    return Boolean(result?.success && result.spec)
  }

  function getValidResult(model: string): LLMResult | null {
    if (!isResultValid(model)) {
      return null
    }
    return results.value[model]
  }

  // Store a result
  function storeResult(model: string, result: Omit<LLMResult, 'timestamp'>): void {
    results.value[model] = {
      ...result,
      timestamp: Date.now(),
    }
    modelStates.value[model] = result.success ? 'ready' : 'error'
    modelPhases.value[model] = result.success ? 'ready' : 'error'
  }

  function setModelPhase(model: string, phase: ModelLoadPhase): void {
    modelPhases.value[model] = phase
  }

  function resetModelPhases(modelsToReset?: string[]): void {
    const target = modelsToReset ?? [...MODELS]
    target.forEach((model) => {
      modelPhases.value[model] = 'idle'
    })
  }

  // Set model state
  function setModelState(model: string, state: ModelState): void {
    modelStates.value[model] = state
  }

  // Set all models to a state
  function setAllModelsState(state: ModelState, modelsToSet?: string[]): void {
    const targetModels = modelsToSet || [...MODELS]
    targetModels.forEach((model) => {
      modelStates.value[model] = state
    })
  }

  // Switch to a different model's result
  async function switchToModel(model: string): Promise<boolean> {
    const result = getValidResult(model)
    if (!result || !result.success || !result.spec) {
      console.warn(`[LLMResults] Cannot switch to ${model}: no valid result`)
      return false
    }

    // Normalize diagram type
    let diagramType = result.diagramType || expectedDiagramType.value
    if (diagramType === 'mind_map') {
      diagramType = 'mindmap'
    }

    if (!diagramType) {
      console.warn(`[LLMResults] Cannot switch to ${model}: no diagram type`)
      return false
    }

    const savedDiagramsStore = useSavedDiagramsStore()

    // During auto-complete: per-model autosave runs on llm:model_completed; skip
    // save-before-replace on programmatic first-result render. User-initiated switch
    // (after generation): save current so user can revert — do not block first paint.
    if (!isGenerating.value) {
      void savedDiagramsStore.saveCurrentDiagramBeforeReplace()
    }

    // Flow map: preserve current orientation (LLM spec typically omits it, defaulting to horizontal)
    // Mind map: preserve theme / diagram style / canvas (LLM/vision specs omit them).
    let specToLoad = result.spec
    const currentData = diagramStore.data as Record<string, unknown> | null
    if (diagramType === 'flow_map') {
      const currentOrientation = currentData?.orientation ?? 'horizontal'
      specToLoad = { ...result.spec, orientation: currentOrientation }
    } else if (isMindMapDiagramType(diagramType)) {
      specToLoad = mergeMindMapPresentationExtrasIntoSpec(result.spec, currentData)
    }

    const topicLock = (lockedTopic.value || '').trim()
    if (topicLock) {
      specToLoad = applyLockedTopicToSpec(specToLoad, topicLock, diagramType)
    }

    // Always zoom-fit after model switch so different LLM layouts are framed.
    // Fit runs from diagram:loaded after mind-map measure-batch settle (v2).
    const softMindMapSwitch =
      isMindMapDiagramType(diagramType) &&
      Array.isArray(specToLoad.nodes) &&
      (specToLoad.nodes as unknown[]).length > 0 &&
      Array.isArray(specToLoad.connections) &&
      (specToLoad.connections as unknown[]).length > 0

    // Mark before load so auto-save skips: content change is programmatic replace,
    // not a user edit. save-before-replace already saved user edits.
    contentChangeIsFromModelSwitch.value = true
    const loaded = diagramStore.loadFromSpec(
      specToLoad,
      diagramType as import('@/types').DiagramType,
      {
        preserveMindMapMeasures: softMindMapSwitch,
        preferLaidOutMindMapNodes: softMindMapSwitch,
      }
    )
    if (loaded) {
      selectedModel.value = model
      rememberPreferredModel(model)
      if (isGenerating.value) {
        pinnedDuringRun.value = model
      }
      // Defer stamp so getSpecForSave does not block first paint after soft load.
      void nextTick(() => {
        const stamped = diagramStore.getSpecForSave()
        if (stamped) {
          updateCurrentModelSpec(stamped)
        }
      })
      // Always keep activeDiagramId - we're updating the same diagram with different
      // LLM result. Clearing it caused duplicate CREATE when debounced save fired.
      return true
    }

    contentChangeIsFromModelSwitch.value = false
    if (import.meta.env.DEV) {
      console.error(`[LLMResults] Failed to load ${model} result into diagram store`)
    }
    return false
  }

  // Clear cached model results without aborting in-flight AutoComplete streams.
  function clearCachedResultsOnly(): void {
    results.value = {}
    selectedModel.value = null
    totalModels.value = null
    lockedTopic.value = null
    paintedThisSession.value = null
    pinnedDuringRun.value = null
    acceptedThisRun.value = {}
    runErrors.value = {}
  }

  function rememberPreferredModel(model: string | null): void {
    if (model) preferredModel.value = model
  }

  function applyLockedTopicToSpec(
    spec: Record<string, unknown>,
    topic: string,
    diagramType: string
  ): Record<string, unknown> {
    const normalized = diagramType === 'mind_map' ? 'mindmap' : diagramType
    if (
      normalized === 'mindmap' ||
      normalized === 'bubble_map' ||
      normalized === 'circle_map' ||
      normalized === 'tree_map'
    ) {
      return { ...spec, topic }
    }
    if (normalized === 'brace_map') {
      return { ...spec, whole: topic, topic }
    }
    if (normalized === 'flow_map') {
      return { ...spec, title: topic }
    }
    if (normalized === 'multi_flow_map') {
      return { ...spec, event: topic }
    }
    return spec
  }

  // Clear all cached results and abort any in-flight auto-complete requests.
  function clearCache(): void {
    cancelAllRequests()
    clearCachedResultsOnly()
  }

  // Menu choice. Stamp the painted model first so a later switch still has its edits.
  function setSelectedModel(model: string | null): void {
    if (model !== selectedModel.value && !isGenerating.value) {
      const spec = diagramStore.getSpecForSave()
      if (spec) {
        updateCurrentModelSpec(spec)
      }
    }
    selectedModel.value = model
    preferredModel.value = model
  }

  function abortInFlightRequests(): void {
    abortControllers.value.forEach((controller) => {
      controller.abort()
    })
    abortControllers.value = []
  }

  // Cancel all active requests
  function settleModelAfterStop(model: string): void {
    if (isResultValid(model)) {
      modelStates.value[model] = 'ready'
      modelPhases.value[model] = 'ready'
      return
    }
    modelStates.value[model] = 'idle'
    modelPhases.value[model] = 'idle'
  }

  function cancelAllRequests(): void {
    abortInFlightRequests()
    const modelsToSettle = new Set([
      ...Object.keys(modelStates.value),
      ...Object.keys(results.value),
      ...MODELS,
    ])
    modelsToSettle.forEach((model) => {
      settleModelAfterStop(model)
    })
    isGenerating.value = false
  }

  /**
   * Start one model's run. Other models' saved responses stay so the user can
   * switch back. This model's previous spec stays until a new success replaces it.
   */
  function startGeneration(
    newSessionId: string,
    diagramType: string,
    modelsToRun?: string[],
    topicToLock?: string | null
  ): void {
    abortInFlightRequests()

    isGenerating.value = true
    sessionId.value = newSessionId
    acceptedThisRun.value = {}
    runErrors.value = {}
    paintedThisSession.value = null
    pinnedDuringRun.value = null
    const trimmedLock = typeof topicToLock === 'string' ? topicToLock.trim() : ''
    lockedTopic.value = trimmedLock || null

    // Normalize diagram type
    let normalizedType = diagramType
    if (normalizedType === 'mind_map') {
      normalizedType = 'mindmap'
    }
    expectedDiagramType.value = normalizedType

    const targetModels = modelsToRun || [...MODELS]
    totalModels.value = targetModels.length
    if (selectedModel.value && targetModels.includes(selectedModel.value)) {
      selectedModel.value = null
    }
    setAllModelsState('loading', targetModels)
    targetModels.forEach((model) => {
      modelPhases.value[model] = 'sending'
    })
  }

  // Handle successful model result
  async function handleModelSuccess(
    model: string,
    spec: Record<string, unknown>,
    diagramType: string,
    elapsed: number,
    forSessionId?: string | null
  ): Promise<boolean> {
    if (!isLlmResultForCurrentSession(sessionId.value, forSessionId)) {
      return false
    }

    const currentDiagramType = diagramStore.type
    let normalizedCurrentType = currentDiagramType
    if (normalizedCurrentType === 'mind_map') {
      normalizedCurrentType = 'mindmap'
    }

    if (normalizedCurrentType !== expectedDiagramType.value) {
      if (import.meta.env.DEV) {
        console.warn(`[LLMResults] Diagram type changed during ${model} generation`)
      }
      return false
    }

    const aiLevelStore = useAiContentLevelStore()
    const savedDiagramsStore = useSavedDiagramsStore()
    const generatedLevel = aiLevelStore.getGeneratedLevel(
      aiLevelStore.diagramKey(savedDiagramsStore.activeDiagramId)
    )
    storeResult(model, {
      success: true,
      spec: attachLlmExportAttribution(spec, model, generatedLevel ?? aiLevelStore.level),
      diagramType,
      elapsed,
    })
    acceptedThisRun.value = { ...acceptedThisRun.value, [model]: true }

    const isFirstPaint = paintedThisSession.value === null
    if (
      !shouldPaintCompletedLlmModel({
        paintedModel: paintedThisSession.value,
        selectedModel: selectedModel.value,
        completedModel: model,
        pinnedModel: pinnedDuringRun.value,
      })
    ) {
      return true
    }
    if (isFirstPaint) {
      selectedModel.value = model
      rememberPreferredModel(model)
    }
    const loaded = await switchToModel(model)
    if (!isLlmResultForCurrentSession(sessionId.value, forSessionId)) {
      return false
    }
    if (loaded) {
      paintedThisSession.value = model
    } else if (isFirstPaint && selectedModel.value === model) {
      selectedModel.value = null
    }
    return loaded
  }

  function handleModelError(
    model: string,
    error: string,
    elapsed: number,
    errorType?: string,
    forSessionId?: string | null
  ): void {
    if (!isLlmResultForCurrentSession(sessionId.value, forSessionId)) {
      return
    }
    runErrors.value = {
      ...runErrors.value,
      [model]: { error, errorType },
    }
    const previous = results.value[model]
    if (previous?.success && previous.spec) {
      modelStates.value[model] = 'ready'
      modelPhases.value[model] = 'ready'
      return
    }
    storeResult(model, {
      success: false,
      error,
      errorType,
      elapsed,
    })
  }

  function runSuccessCount(models: string[]): number {
    return models.filter((model) => acceptedThisRun.value[model]).length
  }

  function runErrorFor(model: string): { error: string; errorType?: string } | null {
    return runErrors.value[model] ?? null
  }

  // Complete generation (called when all models finish)
  function completeGeneration(): void {
    isGenerating.value = false

    Object.entries(modelStates.value).forEach(([model, state]) => {
      if (state === 'loading') {
        settleModelAfterStop(model)
      }
    })
  }

  // Add abort controller for tracking
  function addAbortController(controller: AbortController): void {
    abortControllers.value.push(controller)
  }

  // Remove abort controller
  function removeAbortController(controller: AbortController): void {
    const index = abortControllers.value.indexOf(controller)
    if (index > -1) {
      abortControllers.value.splice(index, 1)
    }
  }

  // Reset store
  function reset(): void {
    cancelAllRequests()
    clearCache()
    preferredModel.value = null
    sessionId.value = null
    expectedDiagramType.value = null
    totalModels.value = null
  }

  /**
   * Get results for persistence (save with diagram spec).
   * Returns { results, selectedModel } when we have 2+ successful results.
   */
  function getResultsForPersistence(): {
    results: Record<string, LLMResult>
    selectedModel: string
  } | null {
    const successResults: Record<string, LLMResult> = {}
    Object.entries(results.value).forEach(([model, r]) => {
      if (r.success && r.spec) {
        successResults[model] = r
      }
    })
    const count = Object.keys(successResults).length
    const selected = resolvePersistedSelectedModel(successResults, selectedModel.value)
    if (count < 2 || !selected) return null
    return clonePersistedLlmResults({
      results: successResults,
      selectedModel: selected,
    })
  }

  /**
   * Update the current model's cached spec with user edits.
   * Called when auto-save or save-before-replace persists the diagram.
   * Ensures model switching loads the edited spec (including user-added branches)
   * instead of the original AI output.
   */
  function updateCurrentModelSpec(spec: Record<string, unknown>): void {
    const model = selectedModel.value
    if (!model || !results.value[model]?.success) return
    if (
      !shouldStampCanvasOntoLlmResult({
        isGenerating: isGenerating.value,
        selectedModel: model,
      })
    ) {
      return
    }
    results.value[model] = {
      ...results.value[model],
      spec: { ...spec },
      timestamp: Date.now(),
    }
  }

  /**
   * Restore LLM results from saved diagram spec.
   * Enables model switching when reopening a diagram that had multiple results.
   * @param saved - { results: Record<model, LLMResult>, selectedModel: string }
   */
  function restoreFromSaved(
    saved: { results?: Record<string, LLMResult>; selectedModel?: string },
    diagramType: string
  ): void {
    if (isGenerating.value) {
      return
    }
    if (!saved || typeof saved !== 'object' || !saved.results) return

    const normalizedType = diagramType === 'mind_map' ? 'mindmap' : diagramType
    expectedDiagramType.value = normalizedType
    results.value = {}
    Object.entries(saved.results).forEach(([model, r]) => {
      if (r && r.success && r.spec) {
        results.value[model] = { ...r, timestamp: Date.now() }
        modelStates.value[model] = 'ready'
        modelPhases.value[model] = 'ready'
      }
    })
    const sel = saved.selectedModel
    const restored = sel && Object.keys(results.value).includes(sel) ? sel : null
    selectedModel.value = restored
    if (restored) preferredModel.value = restored
  }

  const canvasModelChoice = computed(() => selectedModel.value || preferredModel.value)

  return {
    // State
    results,
    modelStates,
    modelPhases,
    selectedModel,
    canvasModelChoice,
    isGenerating,
    contentChangeIsFromModelSwitch,
    sessionId,
    expectedDiagramType,
    totalModels,

    // Getters
    models,
    hasAnyResults,
    readyModels,
    successCount,

    // Actions
    isResultValid,
    getValidResult,
    storeResult,
    setModelState,
    setModelPhase,
    resetModelPhases,
    setAllModelsState,
    switchToModel,
    setSelectedModel,
    clearCache,
    clearCachedResultsOnly,
    cancelAllRequests,
    startGeneration,
    handleModelSuccess,
    handleModelError,
    runSuccessCount,
    runErrorFor,
    completeGeneration,
    addAbortController,
    removeAbortController,
    reset,
    getResultsForPersistence,
    restoreFromSaved,
    updateCurrentModelSpec,
  }
})
