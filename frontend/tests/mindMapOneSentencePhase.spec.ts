import { describe, expect, it } from 'vitest'

import {
  isMindMapCanvasReadyForOneSentenceEdit,
  shouldUseOneSentenceEditFlow,
} from '@/composables/canvasToolbar/mindMapOneSentencePhase'

function diagramStoreStub(overrides: Record<string, unknown> = {}) {
  return {
    type: 'mindmap',
    collabSessionActive: false,
    sessionEditCount: 0,
    data: { nodes: [] },
    ...overrides,
  } as never
}

function savedStoreStub(activeDiagramId: string | null = null) {
  return { activeDiagramId } as never
}

function llmStoreStub(overrides: Record<string, unknown> = {}) {
  return {
    isGenerating: false,
    successCount: 0,
    ...overrides,
  } as never
}

describe('mindMapOneSentencePhase', () => {
  it('detects branch nodes on canvas', () => {
    const store = diagramStoreStub({
      data: {
        nodes: [
          { id: 'topic', type: 'topic', text: '鼠标' },
          { id: 'b1', type: 'branch', text: '按键' },
        ],
      },
    })
    expect(isMindMapCanvasReadyForOneSentenceEdit(store)).toBe(true)
  })

  it('returns false for topic-only canvas', () => {
    const store = diagramStoreStub({
      data: { nodes: [{ id: 'topic', type: 'topic', text: '鼠标' }] },
    })
    expect(isMindMapCanvasReadyForOneSentenceEdit(store)).toBe(false)
  })

  it('uses edit flow for library-bound diagram even before branches hydrate', () => {
    const store = diagramStoreStub({
      data: { nodes: [{ id: 'topic', type: 'topic', text: '鼠标' }] },
    })
    const saved = savedStoreStub('85bf323f-ba86-442c-9e2d-18fcadc341a6')
    const llm = llmStoreStub()
    expect(shouldUseOneSentenceEditFlow(store, saved, llm, 'create')).toBe(true)
  })

  it('uses edit flow once branch nodes exist without library id', () => {
    const store = diagramStoreStub({
      data: {
        nodes: [
          { id: 'topic', type: 'topic', text: '鼠标' },
          { id: 'b1', type: 'branch', text: '按键' },
        ],
      },
    })
    const saved = savedStoreStub(null)
    const llm = llmStoreStub()
    expect(shouldUseOneSentenceEditFlow(store, saved, llm, 'create')).toBe(true)
  })

  it('uses create flow for pristine blank mindmap', () => {
    const store = diagramStoreStub({
      data: { nodes: [{ id: 'topic', type: 'topic', text: '鼠标' }] },
    })
    const saved = savedStoreStub(null)
    const llm = llmStoreStub()
    expect(shouldUseOneSentenceEditFlow(store, saved, llm, 'create')).toBe(false)
  })
})
