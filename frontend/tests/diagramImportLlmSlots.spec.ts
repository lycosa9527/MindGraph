/**
 * .mg import keeps each model's diagram available, and the canvas body does not
 * carry llm_results into the next save.
 */
import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { loadImportedDiagramSpec } from '@/composables/editor/useDiagramImport'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'

describe('loadImportedDiagramSpec', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
  })

  it('restores model slots and leaves them off the canvas spec', () => {
    const loaded = loadImportedDiagramSpec({
      type: 'mindmap',
      topic: 'Open',
      nodes: [
        { id: 'topic', text: 'Open', type: 'topic' },
        { id: 'branch-r-1-0', text: 'Peer', type: 'branch' },
      ],
      connections: [{ id: 'e1', source: 'topic', target: 'branch-r-1-0' }],
      llm_results: {
        selectedModel: 'kimi',
        results: {
          express: {
            success: true,
            spec: { topic: 'express' },
            timestamp: 1,
          },
        },
      },
    })

    expect(loaded).toBe(true)
    const llm = useLLMResultsStore()
    expect(llm.canvasModelChoice).toBe('kimi')
    expect(llm.getValidResult('kimi')?.spec).toMatchObject({ topic: 'Open' })
    expect(llm.getValidResult('express')?.spec).toEqual({ topic: 'express' })

    const saved = useDiagramStore().getSpecForSave()
    expect(saved).not.toHaveProperty('llm_results')
    expect(saved?.nodes).toEqual(
      expect.arrayContaining([expect.objectContaining({ id: 'topic', text: 'Open' })])
    )
  })

  it('drops the previous diagram models when the file has none', () => {
    const llm = useLLMResultsStore()
    llm.storeResult('express', { success: true, spec: { topic: 'old' }, elapsed: 1 })

    const loaded = loadImportedDiagramSpec({
      type: 'mindmap',
      topic: 'Manual',
      nodes: [{ id: 'topic', text: 'Manual', type: 'topic' }],
      connections: [],
    })

    expect(loaded).toBe(true)
    expect(llm.getResultsForPersistence()).toBeNull()
    expect(useDiagramStore().getSpecForSave()).not.toHaveProperty('llm_results')
  })
})
