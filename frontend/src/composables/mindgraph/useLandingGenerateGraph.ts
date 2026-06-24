/**
 * Landing prompt → generate_graph with SSE phase colors and status toasts.
 */
import { ref } from 'vue'

import type { useNotifications } from '@/composables/core/useNotifications'
import {
  extractFailureFromPayload,
  resolveDiagramTypeLabel,
  resolveLandingErrorMessage,
  shouldNotifyLandingError,
  topicPreviewFromPrompt,
  normalizeDiagramTypeForLabel,
} from '@/composables/mindgraph/landingGenerateGraphErrors'
import type { ModelLoadPhase } from '@/stores/llmResults'
import { authFetch } from '@/utils/api'
import {
  consumeGenerateGraphStream,
  type GenerateGraphCompletePayload,
  type GenerateGraphStreamPhase,
} from '@/utils/generateGraphStream'

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

export function useLandingGenerateGraph(options: {
  t: (key: string, params?: Record<string, unknown>) => string
  notify: ReturnType<typeof useNotifications>
}) {
  const loadPhase = ref<ModelLoadPhase>('idle')
  const isGenerating = ref(false)
  let lastNotifiedPhase: LandingNotifyPhase | null = null
  let generatingDetailToastShown = false
  let activeAbortController: AbortController | null = null
  let activeRequestBody: Record<string, unknown> | null = null
  let serverProgressTopic: string | undefined
  let serverProgressDiagramType: string | undefined

  function resetLoadPhase(): void {
    loadPhase.value = 'idle'
    lastNotifiedPhase = null
    generatingDetailToastShown = false
    activeRequestBody = null
    serverProgressTopic = undefined
    serverProgressDiagramType = undefined
  }

  function notifyPhase(phase: LandingNotifyPhase): void {
    if (phase === lastNotifiedPhase) {
      return
    }
    lastNotifiedPhase = phase
    const keyMap: Record<LandingNotifyPhase, LandingPhaseToastKey> = {
      client_sent: 'landing.international.phaseRequestSent',
      accepted: 'landing.international.phaseServerReceived',
      detecting: 'landing.international.phasePleaseWait',
      requirements: 'landing.international.phasePleaseWait',
      progress: 'landing.international.phasePleaseWait',
      waiting: 'landing.international.phasePleaseWait',
      streaming: 'landing.international.phasePleaseWait',
    }
    if (phase === 'waiting' || phase === 'progress') {
      notifyGeneratingDetail()
      return
    }
    options.notify.info(String(options.t(keyMap[phase])), 3500)
  }

  function notifyGeneratingDetail(): void {
    if (generatingDetailToastShown) {
      return
    }
    generatingDetailToastShown = true
    const topic =
      serverProgressTopic ||
      topicPreviewFromPrompt(activeRequestBody?.prompt) ||
      String(options.t('landing.international.topicUnknown'))
    const diagramType = resolveDiagramTypeLabel(
      serverProgressDiagramType ?? activeRequestBody?.diagram_type,
      options.t
    )
    options.notify.info(
      String(
        options.t('landing.international.generatingWithTopic', {
          topic,
          diagramType,
        })
      ),
      5000
    )
  }

  function handleStreamPhase(phase: GenerateGraphStreamPhase): void {
    loadPhase.value = STREAM_TO_LOAD_PHASE[phase]
    notifyPhase(phase)
  }

  function notifySuccessNavigate(): void {
    options.notify.success(String(options.t('landing.international.phaseCompleteNavigate')), 3500)
  }

  function notifyPromptGuidance(): void {
    options.notify.info(String(options.t('landing.international.errorValidation')), 6000)
  }

  function notifyGenerationFailure(error: string, errorType?: string, showGuidance?: boolean): void {
    if (!shouldNotifyLandingError(error, errorType)) {
      return
    }
    const message = resolveLandingErrorMessage(error, errorType, options.t)
    options.notify.error(message, 5000)
    if (showGuidance) {
      notifyPromptGuidance()
    }
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
    if (isGenerating.value) {
      return { ok: false, error: 'Generation already in progress' }
    }

    isGenerating.value = true
    activeRequestBody = requestBody
    generatingDetailToastShown = false
    serverProgressTopic = undefined
    serverProgressDiagramType = undefined
    const payload = {
      request_type: 'diagram_generation',
      ...requestBody,
    }

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
              notifyPhase('progress')
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
        resetLoadPhase()
        return { ok: false, error: 'Cancelled' }
      }
      const message = error instanceof Error ? error.message : 'Unknown error'
      return failGeneration(message, 'generation')
    } finally {
      isGenerating.value = false
    }
  }

  function beginGeneration(): AbortController {
    activeAbortController?.abort()
    activeAbortController = new AbortController()
    return activeAbortController
  }

  function endGeneration(): void {
    activeAbortController = null
    resetLoadPhase()
  }

  function abortGeneration(): void {
    activeAbortController?.abort()
    activeAbortController = null
    isGenerating.value = false
    resetLoadPhase()
  }

  return {
    loadPhase,
    isGenerating,
    generateLandingGraph,
    resetLoadPhase,
    beginGeneration,
    endGeneration,
    abortGeneration,
  }
}
