import { describe, expect, it } from 'vitest'

import {
  buildDiagramSaveGuardState,
  canPerformDiagramSave,
  resolveDiagramSaveBlockReason,
  saveBlockReasonToMessageKey,
  saveFlushFailureMessageKey,
  shouldAutoSaveAfterLlmModelCompleted,
} from '@/composables/editor/diagramSaveFeedback'
import { resolveDiagramTitleForSave } from '@/utils/diagramTitleForSave'

describe('resolveDiagramTitleForSave', () => {
  it('prefers user-edited effective title over topic-derived default', () => {
    expect(resolveDiagramTitleForSave('My Custom Name', 'mindmap', 'en')).toBe('My Custom Name')
  })

  it('falls back to diagram type default when effective title is empty', () => {
    expect(resolveDiagramTitleForSave('', 'mindmap', 'en')).toBe('New Mind Map')
    expect(resolveDiagramTitleForSave(null, 'circle_map', 'zh')).toBe('新圆圈图')
  })

  it('trims whitespace from effective title', () => {
    expect(resolveDiagramTitleForSave('  Renamed  ', 'mindmap', 'en')).toBe('Renamed')
  })
})

describe('diagram save guards and feedback', () => {
  const openGuard = {
    llmGenerating: false,
    subgraphPreviewActive: false,
    subgraphGenerating: false,
    collabSessionActive: false,
    isCollabGuest: false,
  }

  it('blocks save while LLM is generating', () => {
    expect(resolveDiagramSaveBlockReason({ ...openGuard, llmGenerating: true })).toBe(
      'llm_generating'
    )
  })

  it('blocks save while subgraph preview is active or generating', () => {
    expect(
      resolveDiagramSaveBlockReason({ ...openGuard, subgraphPreviewActive: true })
    ).toBe('subgraph_busy')
    expect(
      resolveDiagramSaveBlockReason({ ...openGuard, subgraphGenerating: true })
    ).toBe('subgraph_busy')
  })

  it('blocks save during collab host session and for guests', () => {
    expect(
      resolveDiagramSaveBlockReason({ ...openGuard, collabSessionActive: true })
    ).toBe('collab_active')
    expect(resolveDiagramSaveBlockReason({ ...openGuard, isCollabGuest: true })).toBe(
      'collab_guest'
    )
  })

  it('maps block and flush failure reasons to message keys', () => {
    expect(saveBlockReasonToMessageKey('llm_generating')).toBe('editor.saveWaitForGeneration')
    expect(saveFlushFailureMessageKey({ saved: false, reason: 'error' })).toBe('editor.saveFailed')
    expect(saveFlushFailureMessageKey({ saved: false, reason: 'skipped_guards' })).toBeNull()
  })

  it('allows autosave during LLM generation only when bypass flag is set', () => {
    const duringGeneration = {
      authenticated: true,
      llmGenerating: true,
      subgraphPreviewActive: false,
      subgraphGenerating: false,
      collabSessionActive: false,
      isCollabGuest: false,
      suppressed: false,
      hasTypeAndData: true,
    }
    expect(canPerformDiagramSave(duringGeneration)).toBe(false)
    expect(canPerformDiagramSave({ ...duringGeneration, bypassGeneratingGuard: true })).toBe(true)
  })

  it('blocks save when auth is blocked by offline verification', () => {
    expect(
      canPerformDiagramSave({
        authenticated: false,
        llmGenerating: false,
        subgraphPreviewActive: false,
        subgraphGenerating: false,
        collabSessionActive: false,
        isCollabGuest: false,
        suppressed: false,
        hasTypeAndData: true,
      })
    ).toBe(false)
  })

  it('schedules autosave only after successful LLM model completion', () => {
    expect(shouldAutoSaveAfterLlmModelCompleted(true)).toBe(true)
    expect(shouldAutoSaveAfterLlmModelCompleted(false)).toBe(false)
    expect(shouldAutoSaveAfterLlmModelCompleted(undefined)).toBe(false)
  })

  it('buildDiagramSaveGuardState maps store flags', () => {
    expect(
      buildDiagramSaveGuardState({
        llmGenerating: true,
        subgraphPreviewActive: false,
        subgraphGenerating: false,
        collabSessionActive: false,
        isCollabGuest: false,
      }).llmGenerating
    ).toBe(true)
  })
})
