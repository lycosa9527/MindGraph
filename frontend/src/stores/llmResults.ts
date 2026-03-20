/**
 * LLM Results Store - Pinia store for multi-LLM auto-complete results
 *
 * Migrated from old JavaScript:
 * - llm-autocomplete-manager.js
 * - llm-result-cache.js
 * - llm-progress-renderer.js
 *
 * Features:
 * - Caches results from 3 LLMs (Qwen, DeepSeek, Doubao)
 * - TTL-based cache validation (10 minutes)
 * - First-result-wins rendering
 * - Click to switch between cached results
 * - Per-model loading/ready/error states
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { useDiagramStore } from './diagram'
import { useSavedDiagramsStore } from './savedDiagrams'

// Types
export type ModelState = 'idle' | 'loading' | 'ready' | 'error'

export interface LLMResult {
  success: boolean
  spec?: Record<string, unknown>
  diagramType?: string
  error?: string
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
const MODELS = ['qwen', 'deepseek', 'doubao'] as const
export type LLMModel = (typeof MODELS)[number]

const CACHE_TTL_MS = 10 * 60 * 1000 // 10 minutes

export const useLLMResultsStore = defineStore('llmResults', () => {
  const diagramStore = useDiagramStore()

  // State
  const results = ref<Record<string, LLMResult>>({})
  const modelStates = ref<Record<string, ModelState>>({
    qwen: 'idle',
    deepseek: 'idle',
    doubao: 'idle',
  })
  const selectedModel = ref<string | null>(null)
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

  // Check if a result is still valid (within TTL)
  function isResultValid(model: string): boolean {
    const result = results.value[model]
    if (!result || !result.success) return false

    const age = Date.now() - result.timestamp
    return age < CACHE_TTL_MS
  }

  // Get valid (non-expired) result for a model
  function getValidResult(model: string): LLMResult | null {
    if (!isResultValid(model)) {
      // Clean up expired result
      if (results.value[model]) {
        delete results.value[model]
        modelStates.value[model] = 'idle'
      }
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

    // During auto-complete: skip save-before-replace. User edits already saved; we save once on llm:generation_completed.
    // User-initiated switch (after generation): save current before replacing so user can revert.
    if (!isGenerating.value) {
      await savedDiagramsStore.saveCurrentDiagramBeforeReplace()
    }

    // Flow map: preserve current orientation (LLM spec typically omits it, defaulting to horizontal)
    let specToLoad = result.spec
    if (diagramType === 'flow_map') {
      const currentOrientation =
        (diagramStore.data as Record<string, unknown>)?.orientation ?? 'horizontal'
      specToLoad = { ...result.spec, orientation: currentOrientation }
    }

    // Mark before load so auto-save skips: content change is programmatic replace,
    // not a user edit. save-before-replace already saved user edits.
    contentChangeIsFromModelSwitch.value = true
    const loaded = diagramStore.loadFromSpec(
      specToLoad,
      diagramType as import('@/types').DiagramType
    )
    if (loaded) {
      selectedModel.value = model
      // Always keep activeDiagramId - we're updating the same diagram with different
      // LLM result. Clearing it caused duplicate CREATE when debounced save fired.
      console.log(`[LLMResults] Switched to ${model} result`)
      return true
    }

    contentChangeIsFromModelSwitch.value = false
    console.error(`[LLMResults] Failed to load ${model} result into diagram store`)
    return false
  }

  // Clear all cached results
  function clearCache(): void {
    results.value = {}
    modelStates.value = {
      qwen: 'idle',
      deepseek: 'idle',
      doubao: 'idle',
    }
    selectedModel.value = null
    totalModels.value = null
  }

  // Set selected model (for pre-selection, e.g. concept map relationship)
  function setSelectedModel(model: string | null): void {
    selectedModel.value = model
  }

  // Cancel all active requests
  function cancelAllRequests(): void {
    abortControllers.value.forEach((controller) => {
      controller.abort()
    })
    abortControllers.value = []
    setAllModelsState('idle')
    isGenerating.value = false
  }

  // Start generation (called before parallel API calls)
  function startGeneration(
    newSessionId: string,
    diagramType: string,
    modelsToRun?: string[]
  ): void {
    // Cancel any existing requests
    cancelAllRequests()

    // Clear previous cache
    clearCache()

    // Set state
    isGenerating.value = true
    sessionId.value = newSessionId

    // Normalize diagram type
    let normalizedType = diagramType
    if (normalizedType === 'mind_map') {
      normalizedType = 'mindmap'
    }
    expectedDiagramType.value = normalizedType

    // Set loading state for models that will run
    const targetModels = modelsToRun || [...MODELS]
    totalModels.value = targetModels.length
    setAllModelsState('loading', targetModels)
  }

  // Handle successful model result
  async function handleModelSuccess(
    model: string,
    spec: Record<string, unknown>,
    diagramType: string,
    elapsed: number
  ): Promise<boolean> {
    // Verify context hasn't changed
    const currentDiagramType = diagramStore.type
    let normalizedCurrentType = currentDiagramType
    if (normalizedCurrentType === 'mind_map') {
      normalizedCurrentType = 'mindmap'
    }

    if (normalizedCurrentType !== expectedDiagramType.value) {
      console.warn(`[LLMResults] Diagram type changed during ${model} generation`)
      return false
    }

    // Store result
    storeResult(model, {
      success: true,
      spec,
      diagramType,
      elapsed,
    })

    // If this is the first successful result, render it
    // Claim selectedModel synchronously before await to prevent race when two LLMs complete together
    if (selectedModel.value === null) {
      selectedModel.value = model
      const loaded = await switchToModel(model)
      if (!loaded) {
        selectedModel.value = null
      } else {
        console.log(`[LLMResults] First result from ${model} rendered`)
      }
      return loaded
    }

    return true
  }

  // Handle model error
  function handleModelError(model: string, error: string, elapsed: number): void {
    storeResult(model, {
      success: false,
      error,
      elapsed,
    })
  }

  // Complete generation (called when all models finish)
  function completeGeneration(): void {
    isGenerating.value = false

    // Clear loading states for any models still loading
    Object.entries(modelStates.value).forEach(([model, state]) => {
      if (state === 'loading') {
        modelStates.value[model] = 'idle'
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
    if (count < 2 || !selectedModel.value) return null
    return {
      results: successResults,
      selectedModel: selectedModel.value,
    }
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
    if (!saved || typeof saved !== 'object' || !saved.results) return

    const normalizedType = diagramType === 'mind_map' ? 'mindmap' : diagramType
    expectedDiagramType.value = normalizedType
    results.value = {}
    Object.entries(saved.results).forEach(([model, r]) => {
      if (r && r.success && r.spec) {
        results.value[model] = { ...r, timestamp: Date.now() }
        modelStates.value[model] = 'ready'
      }
    })
    const sel = saved.selectedModel
    selectedModel.value = sel && Object.keys(results.value).includes(sel) ? sel : null
  }

  return {
    // State
    results,
    modelStates,
    selectedModel,
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
    setAllModelsState,
    switchToModel,
    setSelectedModel,
    clearCache,
    cancelAllRequests,
    startGeneration,
    handleModelSuccess,
    handleModelError,
    completeGeneration,
    addAbortController,
    removeAbortController,
    reset,
    getResultsForPersistence,
    restoreFromSaved,
    updateCurrentModelSpec,
  }
})
