/**
 * Persist / restore each canvas model's diagram on the spec.
 *
 * The open canvas is one model slot. Every other successful model is another
 * slot, so N models are N diagrams. That count follows the results, not the
 * current menu. The size cap is the only ceiling. A slot that still cannot
 * fit is dropped, largest first. The open diagram stays.
 */
import { SAVE } from '@/config'

import type { LLMResult } from './llmResults'

export interface PersistedLlmResults {
  results: Record<string, LLMResult>
  selectedModel: string
  /**
   * True when the canvas body is that model's diagram, so the file must not
   * store a second copy. False keeps every spec, including the menu model.
   */
  canvasOwnsSelected?: boolean
}

export interface SavedLlmResultsPayload {
  results?: Record<string, LLMResult>
  selectedModel?: string
}

function specSizeKb(spec: Record<string, unknown>): number {
  return new Blob([JSON.stringify(spec)]).size / 1024
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export interface ResolvedPersistedSelection {
  selectedModel: string | null
  canvasOwnsSelected: boolean
}

/**
 * The canvas slot wins. A menu id is remembered only when that model has a
 * spec. Never substitute some other model's key — that would save the open
 * diagram under the wrong name and drop the real spec.
 */
export function resolvePersistedSelectedModel(
  successResults: Record<string, LLMResult>,
  menuModel: string | null,
  canvasSlotModel: string | null
): ResolvedPersistedSelection {
  if (canvasSlotModel && successResults[canvasSlotModel]?.spec) {
    return { selectedModel: canvasSlotModel, canvasOwnsSelected: true }
  }
  if (menuModel && successResults[menuModel]?.spec) {
    return { selectedModel: menuModel, canvasOwnsSelected: false }
  }
  return { selectedModel: null, canvasOwnsSelected: false }
}

export function canvasSpecMatchesSaved(
  savedSpec: Record<string, unknown> | undefined,
  canvasSpec: Record<string, unknown>
): boolean {
  const canvas = { ...canvasSpec }
  delete canvas.llm_results
  return JSON.stringify(savedSpec ?? null) === JSON.stringify(canvas)
}

export function clonePersistedLlmResults(persisted: PersistedLlmResults): PersistedLlmResults {
  return cloneJson(persisted)
}

/**
 * The canvas spec is the selected model's slot. Every other successful model
 * is an extra slot, including a model added after this file was written.
 * One model stays one diagram. A model that cannot fit is dropped, largest
 * first. The open diagram is kept.
 */
export function attachLlmResultsWithinSizeLimit(
  base: Record<string, unknown>,
  persisted: PersistedLlmResults | null,
  maxSizeKb: number
): Record<string, unknown> {
  if (!persisted) return base

  const selected = persisted.selectedModel
  const ownsCanvas = persisted.canvasOwnsSelected !== false && Boolean(selected)
  const omit = ownsCanvas ? selected : ''
  const peersByLargest = Object.keys(persisted.results)
    .filter((model) => model !== omit && persisted.results[model]?.spec)
    .sort((left, right) => {
      const leftKb = specSizeKb({
        spec: persisted.results[left]?.spec ?? {},
      })
      const rightKb = specSizeKb({
        spec: persisted.results[right]?.spec ?? {},
      })
      return rightKb - leftKb
    })

  if (peersByLargest.length === 0 && !selected) return base

  for (let drop = 0; drop <= peersByLargest.length; drop += 1) {
    const keepPeers = peersByLargest.slice(drop)
    const results: Record<string, LLMResult> = {}
    keepPeers.forEach((model) => {
      const row = persisted.results[model]
      if (row) {
        results[model] = row
      }
    })
    const withLlm = {
      ...base,
      llm_results: { results, selectedModel: selected },
    }
    if (specSizeKb(withLlm) <= maxSizeKb) {
      if (drop > 0) {
        console.warn(
          `[llmResults] Dropped ${drop} model diagram(s) to fit the ${maxSizeKb}KB save limit`
        )
      }
      return withLlm
    }
  }
  return base
}

/** Canvas body stays at 500KB. Specs that also store model diagrams use the higher cap. */
export function diagramSpecExceedsSaveLimit(spec: Record<string, unknown>): string | null {
  const llm = spec.llm_results
  const hasLlm = llm !== null && typeof llm === 'object'
  if (!hasLlm) {
    const sizeKb = specSizeKb(spec)
    if (sizeKb > SAVE.MAX_SPEC_SIZE_KB) {
      return `Diagram data too large (${sizeKb.toFixed(0)}KB). Maximum is ${SAVE.MAX_SPEC_SIZE_KB}KB.`
    }
    return null
  }
  const canvas = { ...spec }
  delete canvas.llm_results
  const canvasKb = specSizeKb(canvas)
  if (canvasKb > SAVE.MAX_SPEC_SIZE_KB) {
    return `Diagram data too large (${canvasKb.toFixed(0)}KB). Maximum is ${SAVE.MAX_SPEC_SIZE_KB}KB.`
  }
  const fullKb = specSizeKb(spec)
  if (fullKb > SAVE.MAX_SPEC_WITH_LLM_RESULTS_KB) {
    return `Diagram data too large (${fullKb.toFixed(0)}KB). Maximum is ${SAVE.MAX_SPEC_WITH_LLM_RESULTS_KB}KB.`
  }
  return null
}

/** Pull ``llm_results`` off a library spec so loadFromSpec does not nest them. */
export function splitSavedLlmResultsFromSpec(spec: Record<string, unknown>): {
  specForLoad: Record<string, unknown>
  saved: SavedLlmResultsPayload | null
} {
  const llmResults = spec.llm_results as SavedLlmResultsPayload | undefined
  if (llmResults?.results && typeof llmResults.results === 'object') {
    const specForLoad = { ...spec }
    delete specForLoad.llm_results
    return { specForLoad, saved: llmResults }
  }
  return { specForLoad: spec, saved: null }
}
