/**
 * Persist / restore multi-LLM auto-complete results on the diagram spec.
 *
 * Three full mind-map specs often exceed SAVE.MAX_SPEC_SIZE_KB. The old
 * all-or-nothing attach then wrote a spec *without* ``llm_results``, which
 * overwrote the earlier 2-model save. Pack selected + as many peers as fit.
 */
import type { LLMResult } from './llmResults'

export interface PersistedLlmResults {
  results: Record<string, LLMResult>
  selectedModel: string
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

/** Prefer the painted model; if it is missing, first successful key. */
export function resolvePersistedSelectedModel(
  successResults: Record<string, LLMResult>,
  selectedModel: string | null
): string | null {
  if (selectedModel && successResults[selectedModel]) {
    return selectedModel
  }
  const keys = Object.keys(successResults)
  return keys[0] ?? null
}

export function clonePersistedLlmResults(
  persisted: PersistedLlmResults
): PersistedLlmResults {
  return cloneJson(persisted)
}

/**
 * Attach ``llm_results`` when 2+ models fit under ``maxSizeKb``.
 * Drops largest non-selected peers first; never attaches a 1-model blob.
 */
export function attachLlmResultsWithinSizeLimit(
  base: Record<string, unknown>,
  persisted: PersistedLlmResults | null,
  maxSizeKb: number
): Record<string, unknown> {
  if (!persisted) return base

  const selected = persisted.selectedModel
  const selectedRow = persisted.results[selected]
  if (!selectedRow) return base

  const othersByLargest = Object.keys(persisted.results)
    .filter((model) => model !== selected)
    .sort((left, right) => {
      const leftKb = specSizeKb({
        spec: persisted.results[left]?.spec ?? {},
      })
      const rightKb = specSizeKb({
        spec: persisted.results[right]?.spec ?? {},
      })
      return rightKb - leftKb
    })

  for (let drop = 0; drop < othersByLargest.length; drop += 1) {
    const keepOthers = othersByLargest.slice(drop)
    const results: Record<string, LLMResult> = {}
    results[selected] = selectedRow
    keepOthers.forEach((model) => {
      const row = persisted.results[model]
      if (row) {
        results[model] = row
      }
    })
    if (Object.keys(results).length < 2) {
      continue
    }
    const withLlm = {
      ...base,
      llm_results: { results, selectedModel: selected },
    }
    if (specSizeKb(withLlm) <= maxSizeKb) {
      return withLlm
    }
  }
  return base
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
