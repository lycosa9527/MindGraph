/**
 * Landing prompt → generate_graph with SSE phase colors and status toasts.
 */
import { onScopeDispose, ref } from 'vue'

import {
  dismissReplacingNotification,
  showReplacingNotification,
} from '@/composables/core/notifications'
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import type { useNotifications } from '@/composables/core/useNotifications'
import {
  extractFailureFromPayload,
  normalizeDiagramTypeForLabel,
  resolveDiagramTypeLabel,
  resolveLandingErrorMessage,
  shouldNotifyLandingError,
  topicPreviewFromPrompt,
} from '@/composables/mindgraph/landingGenerateGraphErrors'
import type { ModelLoadPhase } from '@/stores/llmResults'
import { authFetch } from '@/utils/api'
import {
  type GenerateGraphCompletePayload,
  type GenerateGraphStreamPhase,
  consumeGenerateGraphStream,
} from '@/utils/generateGraphStream'
import {
  noteOrgGenerationCacheResult,
  withOrgGenerationCacheBypass,
} from '@/utils/orgGenerationCache'

const STREAM_TO_LOAD_PHASE: Record<GenerateGraphStreamPhase, ModelLoadPhase> = {
  accepted: 'sending',
  detecting: 'waiting',
  requirements: 'waiting',
  progress: 'waiting',
  waiting: 'waiting',
  streaming: 'streaming',
}

type LandingPhaseToastKey =
  | 'landing.international.phaseRequestSent'
  | 'landing.international.phaseServerReceived'
  | 'landing.international.phasePleaseWait'
  | 'landing.international.phaseCompleteNavigate'

type LandingNotifyPhase = GenerateGraphStreamPhase | 'client_sent'

export type LandingPhaseToastBucket = LandingPhaseToastKey | 'generating_detail' | 'silent'

/**
 * Progress lives on the prompt ring. Only the topic toast is spoken;
 * earlier phases would stack a second card on top of it.
 */
export function resolveLandingPhaseToastBucket(phase: LandingNotifyPhase): LandingPhaseToastBucket {
  if (phase === 'waiting' || phase === 'progress') {
    return 'generating_detail'
  }
  return 'silent'
}

/** Whether a toast bucket should fire given buckets already shown this generation. */
export function shouldShowLandingPhaseToast(
  toastBucket: LandingPhaseToastBucket,
  shownToastBuckets: ReadonlySet<LandingPhaseToastBucket>
): boolean {
  if (toastBucket === 'silent') {
    return false
  }
  if (shownToastBuckets.has(toastBucket)) {
    return false
  }
  if (
    toastBucket === 'landing.international.phasePleaseWait' &&
    shownToastBuckets.has('generating_detail')
  ) {
    return false
  }
  return true
}

/**
 * One landing-prompt flight for the page prompt and the quick-access remote.
 * A surface only cancels the run it started, so unmounting the other leaves it alone.
 */
const loadPhase = ref<ModelLoadPhase>('idle')
const isGenerating = ref(false)
let shownToastBuckets = new Set<LandingPhaseToastBucket>()
let activeAbortController: AbortController | null = null
let activeOwner: object | null = null
let generationId = 0
let activeRequestBody: Record<string, unknown> | null = null
let serverProgressTopic: string | undefined
let serverProgressDiagramType: string | undefined

export type LandingGenerationHandle = {
  signal: AbortSignal
  runId: number
}

export function useLandingGenerateGraph(options: {
  t: UseLanguageTranslate
  notify: ReturnType<typeof useNotifications>
}) {
  const owner = {}

  function resetLoadPhase(): void {
    loadPhase.value = 'idle'
    shownToastBuckets = new Set()
    activeRequestBody = null
    serverProgressTopic = undefined
    serverProgressDiagramType = undefined
  }

  function notifyPhase(phase: LandingNotifyPhase): void {
    const toastBucket = resolveLandingPhaseToastBucket(phase)
    if (!shouldShowLandingPhaseToast(toastBucket, shownToastBuckets)) {
      return
    }
    shownToastBuckets.add(toastBucket)
    if (toastBucket === 'generating_detail') {
      notifyGeneratingDetail()
      return
    }
    showReplacingNotification(String(options.t(toastBucket)), 'info', 3500)
  }

  function notifyGeneratingDetail(): void {
    const topic =
      serverProgressTopic ||
      topicPreviewFromPrompt(activeRequestBody?.prompt) ||
      String(options.t('landing.international.topicUnknown'))
    const diagramType = resolveDiagramTypeLabel(
      serverProgressDiagramType ?? activeRequestBody?.diagram_type,
      options.t
    )
    showReplacingNotification(
      String(
        options.t('landing.international.generatingWithTopic', {
          topic,
          diagramType,
        })
      ),
      'info',
      5000
    )
  }

  function handleStreamPhase(phase: GenerateGraphStreamPhase): void {
    loadPhase.value = STREAM_TO_LOAD_PHASE[phase]
    notifyPhase(phase)
  }

  function notifySuccessNavigate(): void {
    showReplacingNotification(
      String(options.t('landing.international.phaseCompleteNavigate')),
      'success',
      3500
    )
  }

  function notifyPromptGuidance(): void {
    showReplacingNotification(
      String(options.t('landing.international.errorValidation')),
      'info',
      6000
    )
  }

  function notifyGenerationFailure(
    error: string,
    errorType?: string,
    showGuidance?: boolean
  ): void {
    if (!shouldNotifyLandingError(error, errorType)) {
      return
    }
    if (showGuidance) {
      notifyPromptGuidance()
      return
    }
    const message = resolveLandingErrorMessage(error, errorType, options.t)
    showReplacingNotification(message, 'error', 5000)
  }

  async function readHttpError(response: Response): Promise<string> {
    const err = await response.json().catch(() => ({ detail: 'Request failed' }))
    return parseHttpErrorDetail(err.detail) || `HTTP ${response.status}`
  }

  function parseHttpErrorDetail(detail: unknown): string | undefined {
    if (typeof detail === 'string') {
      return detail
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => (typeof item === 'object' && item && 'msg' in item ? item.msg : undefined))
        .filter(Boolean)
        .join('; ')
    }
    return undefined
  }

  function parseSuccessResult(
    result: GenerateGraphCompletePayload
  ):
    | { ok: true; result: GenerateGraphCompletePayload; diagramType: string }
    | { ok: false; error: string; errorType?: string; showGuidance?: boolean } {
    const failure = extractFailureFromPayload(result)
    if (failure) {
      return {
        ok: false,
        error: failure.error,
        errorType: failure.errorType,
        showGuidance: result.show_guidance === true,
      }
    }
    const diagramType = normalizeDiagramTypeForLabel(result.diagram_type)
    if (!diagramType) {
      return { ok: false, error: 'No diagram type specified' }
    }
    return { ok: true, result, diagramType }
  }

  function failGeneration(
    error: string,
    errorType?: string,
    showGuidance?: boolean
  ): { ok: false; error: string; errorType?: string } {
    loadPhase.value = 'error'
    notifyGenerationFailure(error, errorType, showGuidance)
    return { ok: false, error, errorType }
  }

  async function generateLandingGraph(
    requestBody: Record<string, unknown>,
    signal?: AbortSignal
  ): Promise<
    | { ok: true; result: GenerateGraphCompletePayload; diagramType: string }
    | { ok: false; error: string; errorType?: string }
  > {
    if (signal !== activeAbortController?.signal) {
      return { ok: false, error: 'Generation already in progress' }
    }

    isGenerating.value = true
    activeRequestBody = requestBody
    shownToastBuckets = new Set()
    serverProgressTopic = undefined
    serverProgressDiagramType = undefined
    const payload = withOrgGenerationCacheBypass({
      request_type: 'diagram_generation',
      ...requestBody,
    })

    loadPhase.value = 'sending'
    notifyPhase('client_sent')

    try {
      const streamResponse = await authFetch('/api/generate_graph/stream', {
        method: 'POST',
        body: JSON.stringify(payload),
        signal,
      })

      if (streamResponse.ok) {
        let streamError: string | undefined
        let streamErrorType: string | undefined
        let completePayload: GenerateGraphCompletePayload | undefined

        const { usedStream } = await consumeGenerateGraphStream(
          streamResponse,
          {
            onPhase: handleStreamPhase,
            onProgress: (metadata) => {
              if (metadata.topic) {
                serverProgressTopic = metadata.topic
              }
              if (metadata.diagram_type) {
                serverProgressDiagramType = metadata.diagram_type
              }
            },
            onComplete: (result) => {
              completePayload = result
            },
            onError: (message, errorType) => {
              streamError = message
              streamErrorType = errorType
            },
          },
          signal
        )

        if (usedStream) {
          if (streamError) {
            return failGeneration(streamError, streamErrorType)
          }
          if (!completePayload) {
            return failGeneration(
              String(options.t('landing.international.errorStreamEmpty')),
              'generation'
            )
          }
          const parsed = parseSuccessResult(completePayload)
          if (parsed.ok) {
            noteOrgGenerationCacheResult(completePayload)
          }
          if (!parsed.ok) {
            return failGeneration(
              parsed.error,
              parsed.errorType ||
                (typeof completePayload.error_type === 'string'
                  ? completePayload.error_type
                  : undefined),
              parsed.showGuidance
            )
          }
          loadPhase.value = 'ready'
          notifySuccessNavigate()
          return parsed
        }
      } else if (streamResponse.status >= 500) {
        return failGeneration(await readHttpError(streamResponse), 'internal')
      } else if (streamResponse.status >= 400) {
        return failGeneration(await readHttpError(streamResponse), 'http')
      }

      loadPhase.value = 'waiting'
      notifyPhase('waiting')

      const response = await authFetch('/api/generate_graph', {
        method: 'POST',
        body: JSON.stringify(payload),
        signal,
      })

      loadPhase.value = 'streaming'
      notifyPhase('streaming')

      if (!response.ok) {
        return failGeneration(await readHttpError(response), 'http')
      }

      const result = (await response.json()) as GenerateGraphCompletePayload & {
        error_type?: string
      }
      const parsed = parseSuccessResult(result)
      if (parsed.ok) {
        noteOrgGenerationCacheResult(result)
      }
      if (!parsed.ok) {
        return failGeneration(
          parsed.error,
          parsed.errorType ||
            (typeof result.error_type === 'string' ? result.error_type : undefined),
          parsed.showGuidance
        )
      }

      loadPhase.value = 'ready'
      notifySuccessNavigate()
      return parsed
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        if (signal && signal === activeAbortController?.signal) {
          resetLoadPhase()
        }
        return { ok: false, error: 'Cancelled' }
      }
      const message = error instanceof Error ? error.message : 'Unknown error'
      return failGeneration(message, 'generation')
    }
  }

  function beginGeneration(): LandingGenerationHandle {
    generationId += 1
    activeAbortController?.abort()
    activeAbortController = new AbortController()
    activeOwner = owner
    isGenerating.value = true
    return { signal: activeAbortController.signal, runId: generationId }
  }

  function releaseRun(handle: LandingGenerationHandle): void {
    if (handle.runId !== generationId) {
      return
    }
    activeAbortController = null
    activeOwner = null
  }

  function endGeneration(handle: LandingGenerationHandle): void {
    if (handle.runId !== generationId) {
      return
    }
    activeAbortController = null
    activeOwner = null
    isGenerating.value = false
    resetLoadPhase()
  }

  function abortOwned(target: object): void {
    if (activeOwner !== target) {
      return
    }
    const controller = activeAbortController
    generationId += 1
    activeAbortController = null
    activeOwner = null
    controller?.abort()
    isGenerating.value = false
    resetLoadPhase()
    if (controller) {
      dismissReplacingNotification()
    }
  }

  function cancelInFlightGeneration(): void {
    if (activeOwner) {
      abortOwned(activeOwner)
      return
    }
    if (!isGenerating.value) {
      return
    }
    generationId += 1
    isGenerating.value = false
    resetLoadPhase()
    dismissReplacingNotification()
  }

  function isCurrentRun(runId: number): boolean {
    return runId === generationId
  }

  onScopeDispose(() => {
    abortOwned(owner)
  })

  return {
    loadPhase,
    isGenerating,
    generateLandingGraph,
    resetLoadPhase,
    beginGeneration,
    releaseRun,
    endGeneration,
    abortGeneration: () => abortOwned(owner),
    cancelInFlightGeneration,
    isCurrentRun,
  }
}
