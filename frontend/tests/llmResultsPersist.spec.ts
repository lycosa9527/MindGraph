import { describe, expect, it } from 'vitest'

import { SAVE } from '@/config'
import type { LLMResult } from '@/stores/llmResults'
import {
  attachLlmResultsWithinSizeLimit,
  diagramSpecExceedsSaveLimit,
  resolvePersistedSelectedModel,
  splitSavedLlmResultsFromSpec,
} from '@/stores/llmResultsPersist'

function resultOf(topic: string, padChars: number): LLMResult {
  return {
    success: true,
    spec: { topic, pad: 'x'.repeat(padChars) },
    timestamp: 1,
  }
}

describe('resolvePersistedSelectedModel', () => {
  const results = {
    qwen: resultOf('q', 1),
    deepseek: resultOf('d', 1),
  }

  it('keeps the canvas slot when that model has a successful spec', () => {
    expect(resolvePersistedSelectedModel(results, 'qwen', 'deepseek')).toEqual({
      selectedModel: 'deepseek',
      canvasOwnsSelected: true,
    })
  })

  it('remembers a menu model that has a spec without claiming the canvas', () => {
    expect(resolvePersistedSelectedModel(results, 'deepseek', null)).toEqual({
      selectedModel: 'deepseek',
      canvasOwnsSelected: false,
    })
  })

  it('does not substitute another model when the menu has no diagram', () => {
    expect(resolvePersistedSelectedModel(results, null, null)).toEqual({
      selectedModel: null,
      canvasOwnsSelected: false,
    })
    expect(resolvePersistedSelectedModel(results, 'doubao', null)).toEqual({
      selectedModel: null,
      canvasOwnsSelected: false,
    })
  })
})

describe('attachLlmResultsWithinSizeLimit', () => {
  it('keeps three model slots without copying the open diagram', () => {
    const persisted = {
      selectedModel: 'qwen',
      results: {
        qwen: resultOf('q', 8),
        deepseek: resultOf('d', 8),
        doubao: resultOf('b', 8),
      },
    }
    const packed = attachLlmResultsWithinSizeLimit({ topic: 'q' }, persisted, 500)
    const llm = packed.llm_results as { results: Record<string, LLMResult>; selectedModel: string }
    expect(llm.selectedModel).toBe('qwen')
    expect(Object.keys(llm.results).sort()).toEqual(['deepseek', 'doubao'])
    expect(llm.results.qwen).toBeUndefined()
    expect(packed.topic).toBe('q')
  })

  it('drops the largest non-selected peer instead of stripping all llm_results', () => {
    const persisted = {
      selectedModel: 'qwen',
      results: {
        qwen: resultOf('q', 40),
        deepseek: resultOf('d', 40),
        doubao: resultOf('b', 8000),
      },
    }
    const withAllKb = new Blob([JSON.stringify({ topic: 't', llm_results: persisted })]).size / 1024
    const twoKb =
      new Blob([
        JSON.stringify({
          topic: 't',
          llm_results: {
            selectedModel: 'qwen',
            results: { qwen: persisted.results.qwen, deepseek: persisted.results.deepseek },
          },
        }),
      ]).size / 1024
    expect(withAllKb).toBeGreaterThan(twoKb)

    const peerOnlyKb =
      new Blob([
        JSON.stringify({
          topic: 't',
          llm_results: {
            selectedModel: 'qwen',
            results: { deepseek: persisted.results.deepseek },
          },
        }),
      ]).size / 1024
    const bothPeersKb =
      new Blob([
        JSON.stringify({
          topic: 't',
          llm_results: {
            selectedModel: 'qwen',
            results: {
              deepseek: persisted.results.deepseek,
              doubao: persisted.results.doubao,
            },
          },
        }),
      ]).size / 1024
    expect(bothPeersKb).toBeGreaterThan(peerOnlyKb)

    const packed = attachLlmResultsWithinSizeLimit(
      { topic: 't' },
      persisted,
      (peerOnlyKb + bothPeersKb) / 2
    )
    const llm = packed.llm_results as
      { results: Record<string, unknown>; selectedModel: string } | undefined
    expect(llm).toBeDefined()
    expect(llm?.selectedModel).toBe('qwen')
    expect(Object.keys(llm?.results ?? {})).toEqual(['deepseek'])
  })

  it('remembers one model without storing a second copy of its diagram', () => {
    const persisted = {
      selectedModel: 'kimi',
      results: { kimi: resultOf('k', 80) },
    }
    const packed = attachLlmResultsWithinSizeLimit({ topic: 'k' }, persisted, 500)
    const llm = packed.llm_results as { results: Record<string, unknown>; selectedModel: string }
    expect(packed.topic).toBe('k')
    expect(llm.selectedModel).toBe('kimi')
    expect(llm.results).toEqual({})
  })

  it("keeps a model that is not on today's menu", () => {
    const ids = ['express', 'qwen3.8-flash', 'qwen3-max', 'kimi', 'doubao21', 'future-model']
    const results: Record<string, LLMResult> = {}
    ids.forEach((id) => {
      results[id] = resultOf(id, 12)
    })
    const packed = attachLlmResultsWithinSizeLimit(
      { topic: 'future-model' },
      { selectedModel: 'future-model', results },
      SAVE.MAX_SPEC_WITH_LLM_RESULTS_KB
    )
    const llm = packed.llm_results as { results: Record<string, LLMResult>; selectedModel: string }
    expect(llm.selectedModel).toBe('future-model')
    expect(Object.keys(llm.results).sort()).toEqual(
      ids.filter((id) => id !== 'future-model').sort()
    )
    expect(llm.results['future-model']).toBeUndefined()
    expect(diagramSpecExceedsSaveLimit(packed)).toBeNull()
  })

  it('keeps every menu model and the last selection when they fit', () => {
    const ids = ['express', 'qwen3.8-flash', 'qwen3-max', 'kimi', 'doubao21']
    const results: Record<string, LLMResult> = {}
    ids.forEach((id) => {
      results[id] = resultOf(id, 20)
    })
    const packed = attachLlmResultsWithinSizeLimit(
      { topic: 't' },
      { selectedModel: 'kimi', results },
      SAVE.MAX_SPEC_WITH_LLM_RESULTS_KB
    )
    const llm = packed.llm_results as { results: Record<string, LLMResult>; selectedModel: string }
    expect(llm.selectedModel).toBe('kimi')
    expect(Object.keys(llm.results).sort()).toEqual(ids.filter((id) => id !== 'kimi').sort())
    expect(llm.results.kimi).toBeUndefined()
    expect(diagramSpecExceedsSaveLimit(packed)).toBeNull()
  })

  it('returns the base spec when even two models exceed the limit', () => {
    const persisted = {
      selectedModel: 'qwen',
      results: {
        qwen: resultOf('q', 8000),
        deepseek: resultOf('d', 8000),
      },
    }
    const packed = attachLlmResultsWithinSizeLimit({ topic: 't' }, persisted, 1)
    const llm = packed.llm_results as { results: Record<string, unknown>; selectedModel: string }
    expect(packed.topic).toBe('t')
    expect(llm.selectedModel).toBe('qwen')
    expect(llm.results).toEqual({})
  })
})

describe('saved model slot round trip', () => {
  it('reopens five models from four extra slots plus the canvas', () => {
    const ids = ['express', 'qwen3.8-flash', 'qwen3-max', 'kimi', 'doubao21']
    const results: Record<string, LLMResult> = {}
    ids.forEach((id) => {
      results[id] = resultOf(id, 12)
    })
    const canvas = { topic: 'kimi', nodes: [{ id: 'topic', text: 'open' }] }
    const packed = attachLlmResultsWithinSizeLimit(
      canvas,
      { selectedModel: 'kimi', results },
      SAVE.MAX_SPEC_WITH_LLM_RESULTS_KB
    )
    const { specForLoad, saved } = splitSavedLlmResultsFromSpec(packed)
    expect(specForLoad.nodes).toEqual(canvas.nodes)
    expect(Object.keys(saved?.results ?? {}).sort()).toEqual(
      ids.filter((id) => id !== 'kimi').sort()
    )
    expect(saved?.selectedModel).toBe('kimi')
    expect(saved?.results?.kimi).toBeUndefined()
  })
})

describe('splitSavedLlmResultsFromSpec', () => {
  it('pulls llm_results off the spec used for loadFromSpec', () => {
    const { specForLoad, saved } = splitSavedLlmResultsFromSpec({
      topic: 't',
      llm_results: {
        selectedModel: 'qwen',
        results: { qwen: resultOf('q', 1), deepseek: resultOf('d', 1) },
      },
    })
    expect(specForLoad.llm_results).toBeUndefined()
    expect(specForLoad.topic).toBe('t')
    expect(saved?.selectedModel).toBe('qwen')
    expect(saved?.results?.deepseek).toBeDefined()
  })

  it('leaves a spec without llm_results unchanged', () => {
    const spec = { topic: 't' }
    expect(splitSavedLlmResultsFromSpec(spec)).toEqual({ specForLoad: spec, saved: null })
  })
})
