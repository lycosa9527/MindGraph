/**
 * Auto-stream Showcase diagram AI copy into form fields.
 *
 * Streams into description + classroom application. Step 2 entry can start
 * generation automatically. Button click while in-flight aborts; idle click
 * clears AI fields and regenerates.
 */
import { type Ref, ref, watch } from 'vue'

import {
  diagramCopyFingerprint,
  streamShowcaseDiagramCopy,
  type ShowcaseDiagramCopyFields,
  type ShowcaseDiagramCopyResult,
} from '@/composables/showcase/generateShowcaseDiagramCopy'
import type { ModelLoadPhase } from '@/stores/llmResults'

type NotifyLike = {
  info: (message: string) => void
  success: (message: string) => void
  error: (message: string) => void
}

type TranslateFn = (key: string) => unknown

type DiagramCopyStreamState = {
  fingerprint: string
  promise: Promise<ShowcaseDiagramCopyResult | void>
  result: ShowcaseDiagramCopyResult | null
  error: string | null
  abort: AbortController
  phaseTimer: ReturnType<typeof setTimeout> | null
  forceOverwrite: boolean
  emptyAtStart: {
    description: boolean
    classroomApplication: boolean
  }
  notifySuccess: boolean
  notifyError: boolean
}

export type DiagramCopySpecSource = {
  specs: Record<string, unknown>[]
  diagramType: string
}

export function useShowcaseDiagramCopyAi(options: {
  t: TranslateFn
  notify: NotifyLike
  caseType: Ref<string>
  title: Ref<string>
  subject: Ref<string>
  grade: Ref<string>
  description: Ref<string>
  classroomApplication: Ref<string>
  resolveSpecSource: () => DiagramCopySpecSource | null
  step?: Ref<number>
}) {
  const { t, notify, caseType, title, subject, grade } = options
  const isGenerating = ref(false)
  const aiGeneratePhase = ref<ModelLoadPhase>('idle')
  const dirtyDescription = ref(false)
  const dirtyClassroomApplication = ref(false)
  let diagramCopyStream: DiagramCopyStreamState | null = null
  let applyingAiFields = false
  let metadataRestartTimer: ReturnType<typeof setTimeout> | null = null

  function isDiagramCaseType(): boolean {
    return caseType.value === 'diagram_case' || caseType.value === 'diagram_template'
  }

  function isStreamInFlight(): boolean {
    if (!diagramCopyStream || diagramCopyStream.result || diagramCopyStream.error) {
      return false
    }
    return (
      isGenerating.value ||
      aiGeneratePhase.value === 'sending' ||
      aiGeneratePhase.value === 'waiting' ||
      aiGeneratePhase.value === 'streaming'
    )
  }

  function clearDiagramCopyPrefetch(): void {
    if (metadataRestartTimer) {
      clearTimeout(metadataRestartTimer)
      metadataRestartTimer = null
    }
    if (diagramCopyStream?.phaseTimer) {
      clearTimeout(diagramCopyStream.phaseTimer)
    }
    diagramCopyStream?.abort.abort()
    diagramCopyStream = null
    isGenerating.value = false
    aiGeneratePhase.value = 'idle'
  }

  function resetDirtyFlags(): void {
    dirtyDescription.value = false
    dirtyClassroomApplication.value = false
  }

  function resetAiCopyFields(): void {
    applyingAiFields = true
    try {
      options.description.value = ''
      options.classroomApplication.value = ''
    } finally {
      applyingAiFields = false
    }
    resetDirtyFlags()
  }

  function markDescriptionDirty(): void {
    if (!applyingAiFields) dirtyDescription.value = true
  }

  function markClassroomApplicationDirty(): void {
    if (!applyingAiFields) dirtyClassroomApplication.value = true
  }

  function applyFinalResult(result: ShowcaseDiagramCopyResult, forceOverwrite: boolean): void {
    applyingAiFields = true
    try {
      if (forceOverwrite || !dirtyDescription.value) {
        options.description.value = result.description
      }
      if (forceOverwrite || !dirtyClassroomApplication.value) {
        options.classroomApplication.value = result.classroomApplication
      }
    } finally {
      applyingAiFields = false
    }
  }

  function applyStreamFields(
    fields: ShowcaseDiagramCopyFields,
    state: DiagramCopyStreamState,
  ): void {
    applyingAiFields = true
    try {
      if (
        fields.description !== undefined &&
        (state.forceOverwrite ||
          (state.emptyAtStart.description && !dirtyDescription.value))
      ) {
        options.description.value = fields.description
      }
      if (
        fields.classroomApplication !== undefined &&
        (state.forceOverwrite ||
          (state.emptyAtStart.classroomApplication && !dirtyClassroomApplication.value))
      ) {
        options.classroomApplication.value = fields.classroomApplication
      }
    } finally {
      applyingAiFields = false
    }
  }

  function scheduleReadyIdle(): void {
    aiGeneratePhase.value = 'ready'
    setTimeout(() => {
      if (aiGeneratePhase.value === 'ready') {
        aiGeneratePhase.value = 'idle'
      }
    }, 900)
  }

  function currentDiagramCopyFingerprint(): string | null {
    if (!isDiagramCaseType()) return null
    const source = options.resolveSpecSource()
    if (!source || source.specs.length < 1) return null
    return diagramCopyFingerprint({
      specs: source.specs,
      title: title.value,
      subject: subject.value,
      grade: grade.value,
      diagramType: source.diagramType,
    })
  }

  function beginDiagramCopyPrefetch(prefetchOptions?: {
    notifyStart?: boolean
    notifySuccess?: boolean
    notifyError?: boolean
    forceOverwrite?: boolean
  }): void {
    if (!isDiagramCaseType()) return
    const source = options.resolveSpecSource()
    if (!source || source.specs.length < 1) return

    const fingerprint = diagramCopyFingerprint({
      specs: source.specs,
      title: title.value,
      subject: subject.value,
      grade: grade.value,
      diagramType: source.diagramType,
    })
    const forceOverwrite = prefetchOptions?.forceOverwrite === true
    const notifySuccess = prefetchOptions?.notifySuccess !== false
    const notifyError = prefetchOptions?.notifyError !== false
    if (
      diagramCopyStream &&
      diagramCopyStream.fingerprint === fingerprint &&
      !diagramCopyStream.error &&
      diagramCopyStream.forceOverwrite === forceOverwrite &&
      !diagramCopyStream.result
    ) {
      return
    }

    clearDiagramCopyPrefetch()
    const abort = new AbortController()
    isGenerating.value = true
    aiGeneratePhase.value = 'sending'
    if (prefetchOptions?.notifyStart) {
      notify.info(String(t('showcase.publishModal.aiGenerating')))
    }

    const phaseTimer = setTimeout(() => {
      if (aiGeneratePhase.value === 'sending') {
        aiGeneratePhase.value = 'waiting'
      }
    }, 450)

    const emptyAtStart = {
      description: !options.description.value.trim(),
      classroomApplication: !options.classroomApplication.value.trim(),
    }

    const state: DiagramCopyStreamState = {
      fingerprint,
      promise: undefined as unknown as Promise<ShowcaseDiagramCopyResult | void>,
      result: null,
      error: null,
      abort,
      phaseTimer,
      forceOverwrite,
      emptyAtStart,
      notifySuccess,
      notifyError,
    }
    diagramCopyStream = state

    state.promise = streamShowcaseDiagramCopy(
      {
        specs: source.specs,
        title: title.value,
        subject: subject.value,
        grade: grade.value,
        diagramType: source.diagramType,
        signal: abort.signal,
      },
      {
        onPhase: (phase) => {
          if (diagramCopyStream?.fingerprint !== fingerprint) return
          if (phase === 'extracting' || phase === 'generating') {
            if (aiGeneratePhase.value === 'sending' || aiGeneratePhase.value === 'idle') {
              aiGeneratePhase.value = 'waiting'
            }
          }
        },
        onFields: (fields) => {
          if (diagramCopyStream?.fingerprint !== fingerprint) return
          if (aiGeneratePhase.value !== 'streaming') {
            aiGeneratePhase.value = 'streaming'
          }
          applyStreamFields(fields, state)
        },
        onDone: (result) => {
          if (diagramCopyStream?.fingerprint !== fingerprint) return
          diagramCopyStream.result = result
          diagramCopyStream.error = null
          applyFinalResult(result, forceOverwrite)
          aiGeneratePhase.value = 'streaming'
        },
      },
    )
      .then((result) => {
        if (diagramCopyStream?.fingerprint !== fingerprint) {
          return result
        }
        diagramCopyStream.result = result
        diagramCopyStream.error = null
        applyFinalResult(result, forceOverwrite)
        if (state.notifySuccess) {
          notify.success(String(t('showcase.publishModal.aiGenerateDiagramSuccess')))
        }
        return result
      })
      .catch((error: unknown) => {
        if (abort.signal.aborted) {
          return
        }
        const message =
          error instanceof Error && error.message
            ? error.message
            : String(t('showcase.publishModal.aiGenerateFailed'))
        if (diagramCopyStream?.fingerprint === fingerprint) {
          diagramCopyStream.error = message
          aiGeneratePhase.value = 'error'
          if (state.notifyError) {
            notify.error(message)
          }
        }
      })
      .finally(() => {
        if (diagramCopyStream?.fingerprint !== fingerprint) return
        if (diagramCopyStream.phaseTimer) {
          clearTimeout(diagramCopyStream.phaseTimer)
          diagramCopyStream.phaseTimer = null
        }
        isGenerating.value = false
        if (aiGeneratePhase.value === 'streaming' || aiGeneratePhase.value === 'ready') {
          scheduleReadyIdle()
        } else if (aiGeneratePhase.value !== 'error') {
          aiGeneratePhase.value = 'idle'
        }
      })
  }

  function generateDiagramCopy(): void {
    if (!title.value.trim()) {
      notify.error(String(t('showcase.publishModal.validationTitle')))
      return
    }
    if (!isDiagramCaseType()) {
      notify.info(String(t('showcase.publishModal.aiGenerateTeachingOnly')))
      return
    }
    const source = options.resolveSpecSource()
    if (!source || source.specs.length < 1) {
      notify.error(String(t('showcase.publishModal.aiGenerateNeedDiagram')))
      return
    }

    if (isStreamInFlight()) {
      clearDiagramCopyPrefetch()
      notify.info(String(t('showcase.publishModal.aiGenerateCancelled')))
      return
    }

    resetAiCopyFields()
    beginDiagramCopyPrefetch({
      notifyStart: true,
      notifySuccess: true,
      notifyError: true,
      forceOverwrite: true,
    })
  }

  watch([title, subject, grade], () => {
    if (!isDiagramCaseType()) return
    if (!diagramCopyStream) return
    const next = currentDiagramCopyFingerprint()
    if (!next || next === diagramCopyStream.fingerprint) return
    if (metadataRestartTimer) {
      clearTimeout(metadataRestartTimer)
    }
    metadataRestartTimer = setTimeout(() => {
      metadataRestartTimer = null
      if (!isDiagramCaseType()) return
      const onStep2 = options.step == null || options.step.value === 2
      const latest = currentDiagramCopyFingerprint()
      if (!latest) return
      if (diagramCopyStream && diagramCopyStream.fingerprint === latest) return
      clearDiagramCopyPrefetch()
      if (onStep2) {
        beginDiagramCopyPrefetch({
          notifyStart: true,
          notifySuccess: true,
          notifyError: true,
          forceOverwrite: false,
        })
      }
    }, 500)
  })

  return {
    isGenerating,
    aiGeneratePhase,
    clearDiagramCopyPrefetch,
    beginDiagramCopyPrefetch,
    generateDiagramCopy,
    resetAiCopyFields,
    markDescriptionDirty,
    markClassroomApplicationDirty,
  }
}
