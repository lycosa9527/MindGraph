/**
 * Audit: why auto-complete’s 3 LLM results sometimes vanish from the library row.
 *
 * Two holes, measured here:
 * 1. Size — all-or-nothing attach. The 3rd model PUT can exceed 500KB and
 *    overwrite a good 2-model save with a spec that has no llm_results.
 * 2. A 16-node map (the session that filed this) is far under 500KB at 3x —
 *    that case is the dirty/switch/drain hole, not the size cap.
 */
import { describe, expect, it } from 'vitest'

import { SAVE } from '@/config'
import { attachLlmResultsWithinSizeLimit } from '@/stores/llmResultsPersist'
import type { LLMResult } from '@/stores/llmResults'

function specSizeKb(spec: Record<string, unknown>): number {
  return new Blob([JSON.stringify(spec)]).size / 1024
}

function buildMindMapSpec(nodeCount: number, textUnits: number): Record<string, unknown> {
  const label = '概念'.repeat(textUnits)
  const nodes = Array.from({ length: nodeCount }, (_, i) => ({
    id: i === 0 ? 'topic' : `n${i}`,
    type: i === 0 ? 'topic' : 'branch',
    text: `${label}-${i}`,
    position: { x: (i % 8) * 180, y: Math.floor(i / 8) * 90 },
    data: {
      label: `${label}-${i}`,
      mindMapUid: `uid-${i}`,
      side: i % 2 === 0 ? 'left' : 'right',
    },
    style: { width: 140, height: 36 },
  }))
  const connections = nodes.slice(1).map((node, i) => ({
    id: `e${i}`,
    source: i === 0 ? 'topic' : `n${i}`,
    target: node.id,
  }))
  return {
    type: 'mindmap',
    topic: label,
    nodes,
    connections,
    _mindmap_theme: 'classic',
    _mindmap_diagram_style: 'balanced',
    _mindmap_canvas: {
      v2: {
        theme: 'classic',
        diagram_style: 'balanced',
        nodes: nodes.map((node) => ({ id: node.id, position: node.position })),
      },
    },
  }
}

function asResult(spec: Record<string, unknown>): LLMResult {
  return { success: true, spec, diagramType: 'mindmap', timestamp: 1 }
}

function persistThree(spec: Record<string, unknown>) {
  return {
    selectedModel: 'qwen',
    results: {
      qwen: asResult(spec),
      deepseek: asResult({ ...spec, topic: `${String(spec.topic)}-ds` }),
      doubao: asResult({
        ...spec,
        topic: `${String(spec.topic)}-db`,
        pad: 'z'.repeat(4000),
      }),
    },
  }
}

function attachAllOrNothing(
  base: Record<string, unknown>,
  persisted: { results: Record<string, LLMResult>; selectedModel: string },
  maxKb: number
): Record<string, unknown> {
  const withLlm = { ...base, llm_results: persisted }
  return specSizeKb(withLlm) <= maxKb ? withLlm : base
}

function llmModelKeys(spec: Record<string, unknown>): string[] {
  const llm = spec.llm_results as { results?: Record<string, unknown> } | undefined
  return Object.keys(llm?.results ?? {}).sort()
}

describe('auto-complete llm_results persist audit', () => {
  it('16-node map (filed session) keeps all 3 models under the 500KB cap', () => {
    const spec = buildMindMapSpec(16, 4)
    const persisted = persistThree(spec)
    const packed = attachLlmResultsWithinSizeLimit(spec, persisted, SAVE.MAX_SPEC_SIZE_KB)
    const kb = specSizeKb(packed)

    expect(kb).toBeLessThan(80)
    expect(llmModelKeys(packed)).toEqual(['deepseek', 'doubao', 'qwen'])
  })

  it('old all-or-nothing 3rd PUT wipes a good 2-model save; packing keeps two', () => {
    let found: {
      spec: Record<string, unknown>
      persisted: ReturnType<typeof persistThree>
      twoKb: number
      threeKb: number
    } | null = null

    for (let textUnits = 20; textUnits <= 200 && !found; textUnits += 20) {
      const spec = buildMindMapSpec(48, textUnits)
      const persisted = persistThree(spec)
      const two = {
        selectedModel: 'qwen' as const,
        results: {
          qwen: persisted.results.qwen,
          deepseek: persisted.results.deepseek,
        },
      }
      const twoKb = specSizeKb({ ...spec, llm_results: two })
      const threeKb = specSizeKb({ ...spec, llm_results: persisted })
      if (twoKb <= SAVE.MAX_SPEC_SIZE_KB && threeKb > SAVE.MAX_SPEC_SIZE_KB) {
        found = { spec, persisted, twoKb, threeKb }
      }
    }

    expect(found).not.toBeNull()
    if (!found) return

    const diskAfterTwo = attachAllOrNothing(found.spec, {
      selectedModel: 'qwen',
      results: {
        qwen: found.persisted.results.qwen,
        deepseek: found.persisted.results.deepseek,
      },
    }, SAVE.MAX_SPEC_SIZE_KB)
    expect(llmModelKeys(diskAfterTwo)).toEqual(['deepseek', 'qwen'])

    const wiped = attachAllOrNothing(found.spec, found.persisted, SAVE.MAX_SPEC_SIZE_KB)
    expect(wiped.llm_results).toBeUndefined()

    const packed = attachLlmResultsWithinSizeLimit(
      found.spec,
      found.persisted,
      SAVE.MAX_SPEC_SIZE_KB
    )
    expect(llmModelKeys(packed)).toEqual(['deepseek', 'qwen'])
    expect(found.threeKb).toBeGreaterThan(SAVE.MAX_SPEC_SIZE_KB)
    expect(found.twoKb).toBeLessThanOrEqual(SAVE.MAX_SPEC_SIZE_KB)
  })
})
