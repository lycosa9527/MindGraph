import { computed } from 'vue'

import { storeToRefs } from 'pinia'

import { useLanguage, useNotifications } from '@/composables'
import { notify } from '@/composables/core/notifications'
import { eventBus } from '@/composables/core/useEventBus'
import {
  enqueueSubgraphApply,
  withSubgraphFetchSlot,
} from '@/composables/editor/mindMapSubgraphApplyQueue'
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import {
  cancelQuietBranchComplete,
  endQuietBranchComplete,
} from '@/composables/kitty/kittyQuietBranchCompleteBatch'
import {
  commitVerifiedLocalDiagramMutation,
  verifySubgraphChildTextsPresent,
} from '@/composables/kitty/diagramEditApply'
import type { DiagramHubPersistDeps } from '@/composables/kitty/diagramEditHubPersist'
import { i18n } from '@/i18n'
import { useDiagramStore, useLLMResultsStore, useSavedDiagramsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { useKittySessionStore } from '@/stores/kittySession'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'
import { useUIStore } from '@/stores/ui'
import { authFetch } from '@/utils/api'
import { findMindMapNodeIdByLabel } from '@/utils/findMindMapNodeIdByLabel'
import { safeRandomUUID } from '@/utils/safeRandomUUID'
import {
  extractFailureFromPayload,
  resolveGenerateGraphErrorMessage,
  shouldNotifyGenerateGraphError,
} from '@/utils/generateGraphErrors'
import {
  extractBranchesFromGeneratedSpec,
  toDirectChildrenOnly,
  type MindMapBranchSpec,
} from '@/utils/mindMapSubgraphMerge'
import {
  collectMindMapSubgraphContext,
  formatMindMapSubgraphPrompt,
  isMindMapSubgraphExpandable,
} from '@/utils/mindMapSubgraphContext'
import {
  beginMindMapSubgraphDebugRun,
  debugMindMapSubgraphMergeLookup,
  endMindMapSubgraphDebugRun,
  mindMapSubgraphDebug,
  mindMapSubgraphDebugError,
  mindMapSubgraphFailureDump,
  summarizeMindMapNodesForDebug,
  type MindMapSubgraphExtractDebug,
  type MindMapSubgraphRequestDebug,
  type MindMapSubgraphResponseDebug,
} from '@/utils/mindMapSubgraphDebug'
import { resolveDiagramLlmModel } from '@/utils/resolveDiagramLlmModel'

const MAX_SUBGRAPH_CHILDREN = 6

type SubgraphNotifier = {
  warning: (message: string) => void
  error: (message: string) => void
  success: (message: string) => void
}

function formatSubgraphErrorMessage(
  rawError: string,
  errorType: string | undefined,
  t: (key: string) => string
): string {
  const message = resolveGenerateGraphErrorMessage(
    rawError,
    errorType,
    t,
    'canvas.subgraphPreview.generationFailed'
  )
  if (message === t('canvas.subgraphPreview.generationFailed')) {
    return message
  }
  return `${t('canvas.subgraphPreview.generationFailed')}：${message}`
}

function notifySubgraphError(
  rawError: string,
  errorType: string | undefined,
  t: (key: string) => string,
  subgraphNotify: SubgraphNotifier
): void {
  if (!shouldNotifyGenerateGraphError(rawError, errorType)) {
    return
  }
  subgraphNotify.error(formatSubgraphErrorMessage(rawError, errorType, t))
}

function buildResponseDebug(
  httpStatus: number,
  result: Record<string, unknown>
): MindMapSubgraphResponseDebug {
  const spec = (result.spec ?? {}) as Record<string, unknown>
  const rawChildren = Array.isArray(spec.children) ? spec.children : []
  const rawSpecChildTexts = rawChildren
    .map((child) => {
      if (!child || typeof child !== 'object') return ''
      const rec = child as Record<string, unknown>
      return String(rec.text ?? rec.label ?? '').trim()
    })
    .filter(Boolean)
  return {
    httpStatus,
    success: result.success as boolean | undefined,
    diagramType: result.diagram_type as string | undefined,
    specKeys: Object.keys(spec),
    specTopic: typeof spec.topic === 'string' ? spec.topic : undefined,
    rawSpecChildrenCount: rawChildren.length,
    rawSpecChildTexts,
    rawResult: result,
  }
}

function isMindMapDiagramType(diagramType: string | null | undefined): boolean {
  return diagramType === 'mindmap' || diagramType === 'mind_map'
}

export type MindMapSubgraphPersistOptions = {
  hubPersist: DiagramHubPersistDeps
  /** Kitty owning-tab: Hub persist is required (rollback on failure). */
  requireHubPersist?: boolean
}

function resolvePasteAnchorNodeId(
  diagramStore: ReturnType<typeof useDiagramStore>,
  preferredNodeId: string,
  anchorLabel: string
): string | null {
  const nodes = diagramStore.data?.nodes
  const connections = diagramStore.data?.connections
  if (nodes?.some((node) => node.id === preferredNodeId)) {
    return preferredNodeId
  }
  if (anchorLabel) {
    return findMindMapNodeIdByLabel(nodes, connections, anchorLabel)
  }
  return null
}

async function applyGeneratedSubgraphBranches(options: {
  diagramStore: ReturnType<typeof useDiagramStore>
  previewStore: ReturnType<typeof useMindMapSubgraphPreviewStore>
  preferredNodeId: string
  jobKey: string
  anchorLabel: string
  generatedBranches: MindMapBranchSpec[]
  historyLabel: string
  persist?: MindMapSubgraphPersistOptions
  /** Kitty: no success toast / no chat dump of generated children. */
  quietSuccess?: boolean
  nodesBeforeCount: number
  llmModel: string
  subgraphPrompt: string
  responseDebug: MindMapSubgraphResponseDebug
  extractDebug: MindMapSubgraphExtractDebug
  t: (key: string) => string
  subgraphNotify: SubgraphNotifier
}): Promise<boolean> {
  const {
    diagramStore,
    previewStore,
    preferredNodeId,
    jobKey,
    anchorLabel,
    generatedBranches,
    historyLabel,
    persist,
    quietSuccess = false,
    nodesBeforeCount,
    llmModel,
    subgraphPrompt,
    responseDebug,
    extractDebug,
    t,
    subgraphNotify,
  } = options

  const pasteNodeId = resolvePasteAnchorNodeId(diagramStore, preferredNodeId, anchorLabel)
  if (!pasteNodeId) {
    mindMapSubgraphDebug('guard', 'aborted: paste anchor missing after re-resolve', {
      preferredNodeId,
      anchorLabel,
    })
    previewStore.finishJob(jobKey)
    if (quietSuccess) {
      endQuietBranchComplete(false)
    } else {
      subgraphNotify.warning(t('canvas.mindMapOneSentence.kittyEditBranchCompleteFailed'))
      eventBus.emit('kitty:diagram_action_completed', {
        action: 'auto_complete_branch',
        ok: false,
        errorCode: 'branch_not_found',
      })
    }
    endMindMapSubgraphDebugRun(false)
    return false
  }

  const expanded = diagramStore.expandMindMapPathToNode(pasteNodeId)
  mindMapSubgraphDebug('paste', 'expandMindMapPathToNode', { nodeId: pasteNodeId, expanded })

  const mergeLookupBeforePaste = debugMindMapSubgraphMergeLookup(
    diagramStore.data?.nodes ?? [],
    diagramStore.data?.connections ?? [],
    pasteNodeId
  )
  mindMapSubgraphDebug('merge', 'lookup immediately before paste', mergeLookupBeforePaste)

  const childTexts = generatedBranches.map((b) => b.text)
  let applied = false
  let verifiedPersistOk = true
  let persistError: string | undefined

  if (persist) {
    const kittySession = useKittySessionStore()
    const commit = await commitVerifiedLocalDiagramMutation({
      apply: () =>
        diagramStore.pasteMindMapClipboardBranches(pasteNodeId, generatedBranches, historyLabel),
      mutationId: safeRandomUUID(),
      verify: (_before, after) => verifySubgraphChildTextsPresent(after, childTexts),
      hubPersist: persist.hubPersist,
      requireHubPersist: persist.requireHubPersist === true,
      hubRevision: kittySession.hubScopeRevision,
      sendAck: kittySession.getMutationAckSender() ?? undefined,
    })
    applied = commit.applied
    verifiedPersistOk = commit.verified === true && commit.hubPersistOk !== false
    persistError = commit.verificationError
    if (commit.hubRevision != null) {
      kittySession.setHubScopeRevision(commit.hubRevision)
    }
  } else {
    applied = diagramStore.pasteMindMapClipboardBranches(
      pasteNodeId,
      generatedBranches,
      historyLabel
    )
  }

  const nodesAfterCount = diagramStore.data?.nodes?.length ?? 0
  mindMapSubgraphDebug('paste', 'pasteMindMapClipboardBranches result', {
    anchorNodeId: pasteNodeId,
    applied,
    verifiedPersistOk,
    persistError,
    nodesBeforeCount,
    nodesAfterCount,
    nodesAdded: nodesAfterCount - nodesBeforeCount,
    diagramAfter: diagramStore.data?.nodes
      ? summarizeMindMapNodesForDebug(
          diagramStore.data.nodes,
          diagramStore.data.connections ?? []
        )
      : null,
  })

  previewStore.finishJob(jobKey)
  if (!applied || !verifiedPersistOk) {
    mindMapSubgraphFailureDump({
      stage: !applied ? 'merge_failed' : 'hub_persist_failed',
      nodeId: pasteNodeId,
      llm: llmModel,
      prompt: subgraphPrompt,
      response: responseDebug,
      extract: extractDebug,
      mergeLookup: mergeLookupBeforePaste,
      generatedBranches,
    })
    if (quietSuccess) {
      endQuietBranchComplete(false)
    } else {
      subgraphNotify.error(
        !applied
          ? t('canvas.subgraphPreview.mergeFailed')
          : t('canvas.mindMapOneSentence.kittyEditPersistFailed')
      )
      eventBus.emit('kitty:diagram_action_completed', {
        action: 'auto_complete_branch',
        ok: false,
        errorCode: !applied ? 'merge_failed' : 'hub_persist_failed',
      })
    }
    endMindMapSubgraphDebugRun(false)
    return false
  }

  diagramStore.expandMindMapPathToNode(pasteNodeId)
  const successSummary = `${historyLabel}：${childTexts.join('、')}`
  if (quietSuccess) {
    // Hub sync without chat spam; one coalesced "branches ready" reply when the wave ends.
    eventBus.emit('kitty:diagram_action_completed', {
      action: 'auto_complete_branch',
      ok: true,
    })
    endQuietBranchComplete(true)
  } else {
    subgraphNotify.success(successSummary)
    eventBus.emit('kitty:diagram_action_completed', {
      action: 'auto_complete_branch',
      ok: true,
      userSummary: successSummary,
    })
  }
  mindMapSubgraphDebug('done', 'subgraph applied successfully', {
    nodeId: pasteNodeId,
    childCount: generatedBranches.length,
    childTexts,
    verifiedPersist: Boolean(persist),
    quietSuccess,
  })
  endMindMapSubgraphDebugRun(true)
  return true
}

async function runMindMapSubgraphGeneration(
  nodeId: string | null,
  deps: {
    diagramStore: ReturnType<typeof useDiagramStore>
    savedDiagramsStore: ReturnType<typeof useSavedDiagramsStore>
    authStore: ReturnType<typeof useAuthStore>
    previewStore: ReturnType<typeof useMindMapSubgraphPreviewStore>
    llmResultsStore: ReturnType<typeof useLLMResultsStore>
    promptLanguage: string
    t: (key: string) => string
    subgraphNotify: SubgraphNotifier
    persist?: MindMapSubgraphPersistOptions
    anchorLabel?: string
    quietSuccess?: boolean
  }
): Promise<boolean> {
  const {
    diagramStore,
    savedDiagramsStore,
    authStore,
    previewStore,
    llmResultsStore,
    promptLanguage,
    t,
    subgraphNotify,
    persist,
    anchorLabel: anchorLabelOpt,
    quietSuccess = false,
  } = deps

  beginMindMapSubgraphDebugRun(nodeId ?? '(null)')

  const failQuietGuard = (): false => {
    if (quietSuccess) {
      endQuietBranchComplete(false)
    }
    endMindMapSubgraphDebugRun(false)
    return false
  }

  if (!nodeId || !isMindMapDiagramType(diagramStore.type)) {
    mindMapSubgraphDebug('guard', 'aborted: missing nodeId or not a mind map', {
      nodeId,
      diagramType: diagramStore.type,
    })
    return failQuietGuard()
  }
  if (previewStore.isGeneratingFor(nodeId)) {
    mindMapSubgraphDebug('guard', 'aborted: generation already in flight for node', { nodeId })
    return failQuietGuard()
  }
  if (!isMindMapSubgraphExpandable(nodeId)) {
    mindMapSubgraphDebug('guard', 'aborted: node not expandable', { nodeId })
    return failQuietGuard()
  }

  if (!authStore.isAuthenticated) {
    mindMapSubgraphDebug('guard', 'aborted: not authenticated')
    if (!quietSuccess) {
      subgraphNotify.warning(t('notification.signInToUse'))
    }
    return failQuietGuard()
  }
  if (diagramStore.collabSessionActive) {
    mindMapSubgraphDebug('guard', 'aborted: collab session active')
    if (!quietSuccess) {
      subgraphNotify.warning(t('canvas.toolbar.collabLiveAiDisabled'))
    }
    return failQuietGuard()
  }

  const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
  const nodeText = (node?.text ?? '').trim()
  if (!nodeText || isPlaceholderText(nodeText)) {
    mindMapSubgraphDebug('guard', 'aborted: empty or placeholder anchor text', {
      nodeId,
      nodeText,
    })
    if (!quietSuccess) {
      subgraphNotify.warning(t('canvas.subgraphPreview.enterNodeTextFirst'))
    }
    return failQuietGuard()
  }

  const data = diagramStore.data
  if (!data?.nodes || !data?.connections) {
    mindMapSubgraphDebug('guard', 'aborted: diagram has no nodes/connections')
    return failQuietGuard()
  }

  const anchorLabel =
    typeof anchorLabelOpt === 'string' && anchorLabelOpt.trim() !== ''
      ? anchorLabelOpt.trim()
      : nodeText

  mindMapSubgraphDebug('context', 'diagram before request', {
    anchor: { nodeId, nodeText },
    diagram: summarizeMindMapNodesForDebug(data.nodes, data.connections),
    mergeLookup: debugMindMapSubgraphMergeLookup(data.nodes, data.connections, nodeId),
  })

  const subgraphContext = collectMindMapSubgraphContext(data.nodes, data.connections, nodeId)
  if (!subgraphContext) {
    mindMapSubgraphDebug('guard', 'aborted: could not build subgraph context', { nodeId })
    if (!quietSuccess) {
      subgraphNotify.warning(t('canvas.subgraphPreview.enterNodeTextFirst'))
    }
    return failQuietGuard()
  }

  mindMapSubgraphDebug('context', 'subgraph context', subgraphContext)

  const { signal, jobKey } = previewStore.beginGeneration(nodeId)
  const nodesBeforeCount = data.nodes.length
  const historyLabel = t('canvas.subgraphPreview.historyLabel')

  try {
    const diagramId = savedDiagramsStore.activeDiagramId
    const llmModel = resolveDiagramLlmModel(llmResultsStore.selectedModel)
    const subgraphPrompt = formatMindMapSubgraphPrompt(subgraphContext, promptLanguage)

    const requestBody: Record<string, unknown> = {
      prompt: subgraphPrompt,
      diagram_type: 'mindmap',
      language: promptLanguage,
      request_type: 'autocomplete',
      llm: llmModel,
      mind_map_topic: subgraphContext.topic || undefined,
      expand_branch: subgraphContext.expandBranch,
      reference_branches:
        subgraphContext.referenceBranches.length > 0
          ? subgraphContext.referenceBranches
          : undefined,
      existing_branch_children:
        subgraphContext.existingChildren.length > 0
          ? subgraphContext.existingChildren
          : undefined,
      parent_branch: subgraphContext.parentBranch,
      ...(diagramId ? { diagram_id: diagramId } : {}),
    }

    const requestDebug: MindMapSubgraphRequestDebug = {
      endpoint: '/api/generate_graph',
      llm: llmModel,
      language: promptLanguage,
      diagramId,
      prompt: subgraphPrompt,
      body: requestBody,
      context: subgraphContext,
    }
    mindMapSubgraphDebug('request', `POST /api/generate_graph → llm=${llmModel}`, requestDebug)

    const response = await withSubgraphFetchSlot(() =>
      authFetch('/api/generate_graph', {
        method: 'POST',
        signal,
        body: JSON.stringify(requestBody),
      })
    )

    if (!response.ok) {
      if (signal.aborted) {
        mindMapSubgraphDebug('error', 'request aborted')
        previewStore.finishJob(jobKey)
        if (quietSuccess) {
          cancelQuietBranchComplete()
        }
        endMindMapSubgraphDebugRun(false)
        return false
      }
      const errorData = await response.json().catch(() => ({ detail: 'Request failed' }))
      const failure = extractFailureFromPayload(errorData)
      mindMapSubgraphFailureDump({
        stage: 'http_error',
        httpStatus: response.status,
        nodeId,
        llm: llmModel,
        prompt: subgraphPrompt,
        errorData,
        failure,
      })
      if (!quietSuccess) {
        if (failure) {
          notifySubgraphError(failure.error, failure.errorType, t, subgraphNotify)
        } else {
          notifySubgraphError(`HTTP ${response.status}`, undefined, t, subgraphNotify)
        }
      }
      previewStore.finishJob(jobKey)
      if (quietSuccess) {
        endQuietBranchComplete(false)
      }
      endMindMapSubgraphDebugRun(false)
      return false
    }

    const result = (await response.json()) as Record<string, unknown>
    const responseDebug = buildResponseDebug(response.status, result)
    mindMapSubgraphDebug('response', 'API JSON response', responseDebug)

    if (signal.aborted) {
      mindMapSubgraphDebug('error', 'aborted after response received')
      previewStore.finishJob(jobKey)
      if (quietSuccess) {
        cancelQuietBranchComplete()
      }
      endMindMapSubgraphDebugRun(false)
      return false
    }
    const payloadFailure = extractFailureFromPayload(result)
    if (payloadFailure) {
      mindMapSubgraphFailureDump({
        stage: 'payload_failure',
        nodeId,
        llm: llmModel,
        prompt: subgraphPrompt,
        response: responseDebug,
        failure: payloadFailure,
      })
      if (!quietSuccess) {
        notifySubgraphError(payloadFailure.error, payloadFailure.errorType, t, subgraphNotify)
      }
      previewStore.finishJob(jobKey)
      if (quietSuccess) {
        endQuietBranchComplete(false)
      }
      endMindMapSubgraphDebugRun(false)
      return false
    }

    const rawExtracted = extractBranchesFromGeneratedSpec(result.spec as Record<string, unknown>)
    const generatedBranches = toDirectChildrenOnly(rawExtracted).slice(0, MAX_SUBGRAPH_CHILDREN)
    const extractDebug: MindMapSubgraphExtractDebug = {
      extractedCount: rawExtracted.length,
      extractedTexts: rawExtracted.map((b) => b.text),
      afterDirectChildrenOnly: generatedBranches,
    }
    mindMapSubgraphDebug('extract', 'branches extracted from spec', extractDebug)

    if (generatedBranches.length === 0) {
      mindMapSubgraphFailureDump({
        stage: 'empty_extract',
        nodeId,
        llm: llmModel,
        prompt: subgraphPrompt,
        response: responseDebug,
        extract: extractDebug,
      })
      if (!quietSuccess) {
        subgraphNotify.warning(t('canvas.subgraphPreview.emptyResult'))
      }
      previewStore.finishJob(jobKey)
      if (quietSuccess) {
        endQuietBranchComplete(false)
      }
      endMindMapSubgraphDebugRun(false)
      return false
    }

    return enqueueSubgraphApply(() =>
      applyGeneratedSubgraphBranches({
        diagramStore,
        previewStore,
        preferredNodeId: nodeId,
        jobKey,
        anchorLabel,
        generatedBranches,
        historyLabel,
        persist,
        quietSuccess,
        nodesBeforeCount,
        llmModel,
        subgraphPrompt,
        responseDebug,
        extractDebug,
        t,
        subgraphNotify,
      })
    )
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      mindMapSubgraphDebug('error', 'fetch aborted', { name: error.name })
      previewStore.finishJob(jobKey)
      if (quietSuccess) {
        cancelQuietBranchComplete()
      }
      endMindMapSubgraphDebugRun(false)
      return false
    }
    const message =
      error instanceof Error ? error.message : t('canvas.subgraphPreview.generationFailed')
    mindMapSubgraphDebugError('unexpected exception', {
      message,
      error,
      nodeId,
    })
    mindMapSubgraphFailureDump({
      stage: 'exception',
      nodeId,
      message,
      error: error instanceof Error ? { name: error.name, stack: error.stack } : error,
    })
    if (!quietSuccess) {
      subgraphNotify.error(message)
    }
    previewStore.finishJob(jobKey)
    if (quietSuccess) {
      endQuietBranchComplete(false)
    }
    endMindMapSubgraphDebugRun(false)
    return false
  }
}

/** Kitty event-bus entry — safe outside Vue ``setup`` (no ``useI18n``). */
export async function generateMindMapSubgraphForNode(
  nodeId: string | null,
  options?: {
    persist?: MindMapSubgraphPersistOptions
    anchorLabel?: string
    /** Skip success toast and Kitty chat dump of generated children. */
    quietSuccess?: boolean
  }
): Promise<boolean> {
  const uiStore = useUIStore()
  const t = i18n.global.t.bind(i18n.global) as (key: string) => string
  return runMindMapSubgraphGeneration(nodeId, {
    diagramStore: useDiagramStore(),
    savedDiagramsStore: useSavedDiagramsStore(),
    authStore: useAuthStore(),
    previewStore: useMindMapSubgraphPreviewStore(),
    llmResultsStore: useLLMResultsStore(),
    promptLanguage: uiStore.promptLanguage,
    t,
    subgraphNotify: notify,
    persist: options?.persist,
    anchorLabel: options?.anchorLabel,
    quietSuccess: options?.quietSuccess === true,
  })
}

export function useMindMapSubgraphSuggest() {
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const authStore = useAuthStore()
  const previewStore = useMindMapSubgraphPreviewStore()
  const llmResultsStore = useLLMResultsStore()
  const { isGenerating } = storeToRefs(previewStore)
  const notifyComposable = useNotifications()
  const { promptLanguage, t } = useLanguage()

  const isMindMap = computed(
    () => diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map'
  )

  async function generateSubgraph(nodeId: string | null): Promise<boolean> {
    return runMindMapSubgraphGeneration(nodeId, {
      diagramStore,
      savedDiagramsStore,
      authStore,
      previewStore,
      llmResultsStore,
      promptLanguage: promptLanguage.value,
      t,
      subgraphNotify: notifyComposable,
    })
  }

  return {
    isGenerating,
    isMindMap,
    generateSubgraph,
  }
}
