import { describe, expect, it } from 'vitest'

import {
  attachLlmResultsWithinSizeLimit,
  resolvePersistedSelectedModel,
  splitSavedLlmResultsFromSpec,
} from '@/stores/llmResultsPersist'
import type { LLMResult } from '@/stores/llmResults'

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

  it('keeps the painted model when it has a successful spec', () => {
    expect(resolvePersistedSelectedModel(results, 'deepseek')).toBe('deepseek')
  })

  it('falls back to the first successful key when selected is missing', () => {
    expect(resolvePersistedSelectedModel(results, null)).toBe('qwen')
    expect(resolvePersistedSelectedModel(results, 'doubao')).toBe('qwen')
  })
})

describe('attachLlmResultsWithinSizeLimit', () => {
  it('keeps all three models when they fit', () => {
    const persisted = {
      selectedModel: 'qwen',
      results: {
        qwen: resultOf('q', 8),
        deepseek: resultOf('d', 8),
        doubao: resultOf('b', 8),
      },
    }
    const packed = attachLlmResultsWithinSizeLimit({ topic: 't' }, persisted, 500)
    const llm = packed.llm_results as { results: Record<string, unknown>; selectedModel: string }
    expect(Object.keys(llm.results).sort()).toEqual(['deepseek', 'doubao', 'qwen'])
    expect(llm.selectedModel).toBe('qwen')
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
    const withAllKb =
      new Blob([JSON.stringify({ topic: 't', llm_results: persisted })]).size / 1024
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

    const packed = attachLlmResultsWithinSizeLimit(
      { topic: 't' },
      persisted,
      (twoKb + withAllKb) / 2
    )
    const llm = packed.llm_results as
      | { results: Record<string, unknown>; selectedModel: string }
      | undefined
    expect(llm).toBeDefined()
    expect(llm?.selectedModel).toBe('qwen')
    expect(Object.keys(llm?.results ?? {}).sort()).toEqual(['deepseek', 'qwen'])
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
    expect(packed).toEqual({ topic: 't' })
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
