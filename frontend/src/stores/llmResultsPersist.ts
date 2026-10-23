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
  /** Dropdown choice to restore. May be a model that has not generated yet. */
  selectedModel: string
  /**
   * Model whose diagram is the open canvas. Omitted from ``results`` so the
   * file does not store that spec twice. Absent on older saves; those treat
   * ``selectedModel`` as the owner.
   */
  canvasModel?: string
  /**
   * True when ``selectedModel`` is the canvas owner, so a reader that does not
   * know ``canvasModel`` still skips a second copy of that spec.
   */
  canvasOwnsSelected?: boolean
}

export interface SavedLlmResultsPayload {
  results?: Record<string, LLMResult>
  selectedModel?: string
  canvasModel?: string
}

function specSizeKb(spec: Record<string, unknown>): number {
  return new Blob([JSON.stringify(spec)]).size / 1024
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export interface ResolvedPersistedSelection {
  selectedModel: string | null
  canvasModel: string | null
  canvasOwnsSelected: boolean
}

/**
 * Menu choice and canvas owner are stored separately.
 * The menu id is kept even when that model has no spec yet.
 * A menu id is not treated as the canvas owner unless it has a spec or it is
 * the slot already on the canvas — that would save the open diagram under the
 * wrong name.
 */
export function resolvePersistedSelectedModel(
  successResults: Record<string, LLMResult>,
  menuModel: string | null,
  canvasSlotModel: string | null
): ResolvedPersistedSelection {
  const canvasOwner =
    canvasSlotModel && successResults[canvasSlotModel]?.spec ? canvasSlotModel : null
  const menu = menuModel?.trim() ? menuModel.trim() : null
  const menuHasSpec = Boolean(menu && successResults[menu]?.spec)
  let selectedModel: string | null = null
  if (canvasOwner && menu) {
    selectedModel = menu
  } else if (canvasOwner) {
    selectedModel = canvasOwner
  } else if (menu && menuHasSpec) {
    selectedModel = menu
  }
  return {
    selectedModel,
    canvasModel: canvasOwner,
    canvasOwnsSelected: Boolean(canvasOwner && selectedModel === canvasOwner),
  }
}

/** Menu highlight and the model that owns the open canvas, including old files. */
export function restoredLlmView(saved: SavedLlmResultsPayload): {
  menuModel: string | null
  canvasOwner: string | null
} {
  const menu = typeof saved.selectedModel === 'string' ? saved.selectedModel.trim() : ''
  const explicit = typeof saved.canvasModel === 'string' ? saved.canvasModel.trim() : ''
  return {
    menuModel: menu || null,
    canvasOwner: explicit || menu || null,
  }
}

export function clonePersistedLlmResults(persisted: PersistedLlmResults): PersistedLlmResults {
  return cloneJson(persisted)
}

function canvasModelOmittedFromResults(persisted: PersistedLlmResults): string {
  const canvasModel = persisted.canvasModel?.trim() ?? ''
  if (canvasModel && persisted.results[canvasModel]?.spec) {
    return canvasModel
  }
  const selected = persisted.selectedModel
  const ownsCanvas = persisted.canvasOwnsSelected !== false && Boolean(selected)
  if (ownsCanvas && selected && persisted.results[selected]?.spec) {
    return selected
  }
  return ''
}

/**
 * The open canvas is one model's diagram and is not copied into ``results``.
 * Every other successful model is an extra slot. A model that cannot fit is
 * dropped, largest first. The open diagram and the menu choice are kept.
 */
export function attachLlmResultsWithinSizeLimit(
  base: Record<string, unknown>,
  persisted: PersistedLlmResults | null,
  maxSizeKb: number
): Record<string, unknown> {
  if (!persisted) return base

  const selected = persisted.selectedModel
  const omit = canvasModelOmittedFromResults(persisted)
  const canvasModel = persisted.canvasModel?.trim() ?? ''
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
    const llmResults: SavedLlmResultsPayload = { results, selectedModel: selected }
    if (canvasModel) {
      llmResults.canvasModel = canvasModel
    }
    const withLlm = {
      ...base,
      llm_results: llmResults,
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
