import type { SaveFlushResult } from '@/composables/editor/useDiagramAutoSave'

export type DiagramSaveBlockReason =
  | 'llm_generating'
  | 'subgraph_busy'
  | 'collab_active'
  | 'collab_guest'

export interface DiagramSaveGuardState {
  llmGenerating: boolean
  subgraphGenerating: boolean
  collabSessionActive: boolean
  isCollabGuest: boolean
}

export interface DiagramSaveEligibility extends DiagramSaveGuardState {
  authenticated: boolean
  suppressed: boolean
  hasTypeAndData: boolean
  bypassGeneratingGuard?: boolean
}

/** Shared guard for autosave, flush, and per-LLM-round persistence. */
export function canPerformDiagramSave(state: DiagramSaveEligibility): boolean {
  if (!state.authenticated || !state.hasTypeAndData) return false
  if (!state.bypassGeneratingGuard && state.llmGenerating) return false
  if (state.subgraphGenerating) return false
  if (state.suppressed) return false
  if (state.isCollabGuest || state.collabSessionActive) return false
  return true
}

export function shouldAutoSaveAfterLlmModelCompleted(success: boolean | undefined): boolean {
  return success === true
}

export function buildDiagramSaveGuardState(deps: {
  llmGenerating: boolean
  subgraphGenerating: boolean
  collabSessionActive: boolean
  isCollabGuest: boolean
}): DiagramSaveGuardState {
  return {
    llmGenerating: deps.llmGenerating,
    subgraphGenerating: deps.subgraphGenerating,
    collabSessionActive: deps.collabSessionActive,
    isCollabGuest: deps.isCollabGuest,
  }
}

export function resolveDiagramSaveBlockReason(
  state: DiagramSaveGuardState
): DiagramSaveBlockReason | null {
  if (state.llmGenerating) return 'llm_generating'
  if (state.subgraphGenerating) return 'subgraph_busy'
  if (state.collabSessionActive) return 'collab_active'
  if (state.isCollabGuest) return 'collab_guest'
  return null
}

export function saveBlockReasonToMessageKey(reason: DiagramSaveBlockReason): string {
  switch (reason) {
    case 'llm_generating':
      return 'editor.saveWaitForGeneration'
    case 'subgraph_busy':
      return 'editor.saveBlockedSubgraphPreview'
    case 'collab_active':
      return 'editor.saveBlockedCollabActive'
    case 'collab_guest':
      return 'editor.saveBlockedCollabGuest'
  }
}

export function saveFlushFailureMessageKey(result: SaveFlushResult): string | null {
  if (result.saved) return null
  switch (result.reason) {
    case 'skipped_empty':
      return 'editor.saveNothingToSave'
    case 'error':
      return 'editor.saveFailed'
    default:
      return null
  }
}

export interface DiagramSaveFlushFeedbackOptions {
  flush: () => Promise<SaveFlushResult>
  guardState: DiagramSaveGuardState
  t: (key: string) => string
  notifySuccess: (message: string) => void
  notifyWarning: (message: string) => void
  onSlotsFull?: () => void
}

export async function flushDiagramSaveWithFeedback(
  options: DiagramSaveFlushFeedbackOptions
): Promise<SaveFlushResult> {
  const blockReason = resolveDiagramSaveBlockReason(options.guardState)
  if (blockReason) {
    options.notifyWarning(options.t(saveBlockReasonToMessageKey(blockReason)))
    return { saved: false, reason: 'skipped_guards' }
  }

  const result = await options.flush()
  if (result.saved) {
    options.notifySuccess(options.t('editor.savedSuccess'))
    return result
  }
  if (result.reason === 'skipped_slots_full') {
    options.onSlotsFull?.()
    return result
  }

  const failureKey = saveFlushFailureMessageKey(result)
  if (failureKey) {
    options.notifyWarning(options.t(failureKey))
  }
  return result
}
