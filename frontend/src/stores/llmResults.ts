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

  // Track abort controllers for cancellation
  const abortControllers = ref<AbortController[]>([])

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
  function switchToModel(model: string): boolean {
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

    // Load into diagram store
    const loaded = diagramStore.loadFromSpec(
      result.spec,
      diagramType as import('@/types').DiagramType
    )
    if (loaded) {
      selectedModel.value = model
      console.log(`[LLMResults] Switched to ${model} result`)
      return true
    }

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
    setAllModelsState('loading', targetModels)
  }

  // Handle successful model result
  function handleModelSuccess(
    model: string,
    spec: Record<string, unknown>,
    diagramType: string,
    elapsed: number
  ): boolean {
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
    if (selectedModel.value === null) {
      const loaded = switchToModel(model)
      if (loaded) {
        console.log(`[LLMResults] First result from ${model} rendered`)
        return true
      }
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
  }

  return {
    // State
    results,
    modelStates,
    selectedModel,
    isGenerating,
    sessionId,
    expectedDiagramType,

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
    clearCache,
    cancelAllRequests,
    startGeneration,
    handleModelSuccess,
    handleModelError,
    completeGeneration,
    addAbortController,
    removeAbortController,
    reset,
  }
})
