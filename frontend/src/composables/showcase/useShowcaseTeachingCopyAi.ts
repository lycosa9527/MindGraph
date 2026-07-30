/**
 * Auto-stream Showcase teaching-design AI copy into form fields.
 *
 * Step 2 entry starts generation automatically. Button click while in-flight
 * aborts; click while idle clears fields and regenerates.
 */
import { type Ref, ref, watch } from 'vue'

import {
  streamShowcaseTeachingCopy,
  teachingCopyFingerprint,
  type ShowcaseTeachingCopyFields,
  type ShowcaseTeachingCopyResult,
} from '@/composables/showcase/generateShowcaseTeachingCopy'
import type { ModelLoadPhase } from '@/stores/llmResults'

type NotifyLike = {
  info: (message: string) => void
  success: (message: string) => void
  error: (message: string) => void
}

type TranslateFn = (key: string) => unknown

type TeachingCopyStreamState = {
  fingerprint: string
  promise: Promise<ShowcaseTeachingCopyResult>
  result: ShowcaseTeachingCopyResult | null
  error: string | null
  abort: AbortController
  phaseTimer: ReturnType<typeof setTimeout> | null
  forceOverwrite: boolean
  emptyAtStart: {
    description: boolean
    designHighlights: boolean
    teachingReflection: boolean
  }
  notifySuccess: boolean
  notifyError: boolean
}

export function useShowcaseTeachingCopyAi(options: {
  t: TranslateFn
  notify: NotifyLike
  caseType: Ref<string>
  title: Ref<string>
  subject: Ref<string>
  grade: Ref<string>
  uploadedFile: Ref<File | null>
  description: Ref<string>
  designHighlights: Ref<string>
  teachingReflection: Ref<string>
  step?: Ref<number>
}) {
  const { t, notify, caseType, title, subject, grade, uploadedFile } = options
  const isGenerating = ref(false)
  const aiGeneratePhase = ref<ModelLoadPhase>('idle')
  const dirtyDescription = ref(false)
  const dirtyDesignHighlights = ref(false)
  const dirtyTeachingReflection = ref(false)
  let teachingCopyStream: TeachingCopyStreamState | null = null
  let applyingAiFields = false
  let metadataRestartTimer: ReturnType<typeof setTimeout> | null = null

  function isStreamInFlight(): boolean {
    if (!teachingCopyStream || teachingCopyStream.result || teachingCopyStream.error) {
      return false
    }
    return (
      isGenerating.value ||
      aiGeneratePhase.value === 'sending' ||
      aiGeneratePhase.value === 'waiting' ||
      aiGeneratePhase.value === 'streaming'
    )
  }

  function clearTeachingCopyPrefetch(): void {
    if (metadataRestartTimer) {
      clearTimeout(metadataRestartTimer)
      metadataRestartTimer = null
    }
    if (teachingCopyStream?.phaseTimer) {
      clearTimeout(teachingCopyStream.phaseTimer)
    }
    teachingCopyStream?.abort.abort()
    teachingCopyStream = null
    isGenerating.value = false
    aiGeneratePhase.value = 'idle'
  }

  function resetDirtyFlags(): void {
    dirtyDescription.value = false
    dirtyDesignHighlights.value = false
    dirtyTeachingReflection.value = false
  }

  function resetAiCopyFields(): void {
    applyingAiFields = true
    try {
      options.description.value = ''
      options.designHighlights.value = ''
      options.teachingReflection.value = ''
    } finally {
      applyingAiFields = false
    }
    resetDirtyFlags()
  }

  function markDescriptionDirty(): void {
    if (!applyingAiFields) dirtyDescription.value = true
  }

  function markDesignHighlightsDirty(): void {
    if (!applyingAiFields) dirtyDesignHighlights.value = true
  }

  function markTeachingReflectionDirty(): void {
    if (!applyingAiFields) dirtyTeachingReflection.value = true
  }

  function applyFinalResult(result: ShowcaseTeachingCopyResult, forceOverwrite: boolean): void {
    applyingAiFields = true
    try {
      if (forceOverwrite || !dirtyDescription.value) {
        options.description.value = result.description
      }
      if (forceOverwrite || !dirtyDesignHighlights.value) {
        options.designHighlights.value = result.designHighlights
      }
      if (forceOverwrite || !dirtyTeachingReflection.value) {
        options.teachingReflection.value = result.teachingReflection
      }
    } finally {
      applyingAiFields = false
    }
  }

  function applyStreamFields(
    fields: ShowcaseTeachingCopyFields,
    state: TeachingCopyStreamState,
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
        fields.designHighlights !== undefined &&
        (state.forceOverwrite ||
          (state.emptyAtStart.designHighlights && !dirtyDesignHighlights.value))
      ) {
        options.designHighlights.value = fields.designHighlights
      }
      if (
        fields.teachingReflection !== undefined &&
        (state.forceOverwrite ||
          (state.emptyAtStart.teachingReflection && !dirtyTeachingReflection.value))
      ) {
        options.teachingReflection.value = fields.teachingReflection
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

  function currentTeachingCopyFingerprint(): string | null {
    const file = uploadedFile.value
    if (!file || caseType.value !== 'teaching_design') return null
    return teachingCopyFingerprint({
      file,
      title: title.value,
      subject: subject.value,
      grade: grade.value,
    })
  }

  function beginTeachingCopyPrefetch(prefetchOptions?: {
    notifyStart?: boolean
    notifySuccess?: boolean
    notifyError?: boolean
    forceOverwrite?: boolean
  }): void {
    const file = uploadedFile.value
    if (!file || caseType.value !== 'teaching_design') return
    const fingerprint = teachingCopyFingerprint({
      file,
      title: title.value,
      subject: subject.value,
      grade: grade.value,
    })
    const forceOverwrite = prefetchOptions?.forceOverwrite === true
    const notifySuccess = prefetchOptions?.notifySuccess !== false
    const notifyError = prefetchOptions?.notifyError !== false
    if (
      teachingCopyStream &&
      teachingCopyStream.fingerprint === fingerprint &&
      !teachingCopyStream.error &&
      teachingCopyStream.forceOverwrite === forceOverwrite &&
      !teachingCopyStream.result
    ) {
      return
    }

    clearTeachingCopyPrefetch()
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
      designHighlights: !options.designHighlights.value.trim(),
      teachingReflection: !options.teachingReflection.value.trim(),
    }

    const state: TeachingCopyStreamState = {
      fingerprint,
      promise: undefined as unknown as Promise<ShowcaseTeachingCopyResult>,
      result: null,
      error: null,
      abort,
      phaseTimer,
      forceOverwrite,
      emptyAtStart,
      notifySuccess,
      notifyError,
    }
    teachingCopyStream = state

    state.promise = streamShowcaseTeachingCopy(
      {
        file,
        title: title.value,
        subject: subject.value,
        grade: grade.value,
        signal: abort.signal,
      },
      {
        onPhase: (phase) => {
          if (teachingCopyStream?.fingerprint !== fingerprint) return
          if (phase === 'extracting' || phase === 'generating') {
            if (aiGeneratePhase.value === 'sending' || aiGeneratePhase.value === 'idle') {
              aiGeneratePhase.value = 'waiting'
            }
          }
        },
        onFields: (fields) => {
          if (teachingCopyStream?.fingerprint !== fingerprint) return
          if (aiGeneratePhase.value !== 'streaming') {
            aiGeneratePhase.value = 'streaming'
          }
          applyStreamFields(fields, state)
        },
        onDone: (result) => {
          if (teachingCopyStream?.fingerprint !== fingerprint) return
          teachingCopyStream.result = result
          teachingCopyStream.error = null
          applyFinalResult(result, forceOverwrite)
          aiGeneratePhase.value = 'streaming'
        },
      },
    )
      .then((result) => {
        if (teachingCopyStream?.fingerprint !== fingerprint) {
          return result
        }
        teachingCopyStream.result = result
        teachingCopyStream.error = null
        applyFinalResult(result, forceOverwrite)
        if (state.notifySuccess) {
          notify.success(String(t('showcase.publishModal.aiGenerateSuccess')))
        }
        return result
      })
      .catch((error: unknown) => {
        if (abort.signal.aborted) {
          throw error
        }
        const message =
          error instanceof Error && error.message
            ? error.message
            : String(t('showcase.publishModal.aiGenerateFailed'))
        if (teachingCopyStream?.fingerprint === fingerprint) {
          teachingCopyStream.error = message
          aiGeneratePhase.value = 'error'
          if (state.notifyError) {
            notify.error(message)
          }
        }
        throw error
      })
      .finally(() => {
        if (teachingCopyStream?.fingerprint !== fingerprint) return
        if (teachingCopyStream.phaseTimer) {
          clearTimeout(teachingCopyStream.phaseTimer)
          teachingCopyStream.phaseTimer = null
        }
        isGenerating.value = false
        if (aiGeneratePhase.value === 'streaming' || aiGeneratePhase.value === 'ready') {
          scheduleReadyIdle()
        } else if (aiGeneratePhase.value !== 'error') {
          aiGeneratePhase.value = 'idle'
        }
      })
  }

  function generateDescription(): void {
    if (!title.value.trim()) {
      notify.error(String(t('showcase.publishModal.validationTitle')))
      return
    }
    if (caseType.value !== 'teaching_design') {
      notify.info(String(t('showcase.publishModal.aiGenerateTeachingOnly')))
      return
    }
    if (!uploadedFile.value) {
      notify.error(String(t('showcase.publishModal.aiGenerateNeedFile')))
      return
    }

    // In-flight: first click aborts (keeps any partial text).
    if (isStreamInFlight()) {
      clearTeachingCopyPrefetch()
      notify.info(String(t('showcase.publishModal.aiGenerateCancelled')))
      return
    }

    // Idle / finished / errored: clear and regenerate.
    resetAiCopyFields()
    beginTeachingCopyPrefetch({
      notifyStart: true,
      notifySuccess: true,
      notifyError: true,
      forceOverwrite: true,
    })
  }

  // Debounced abort/restart when title/subject/grade change on step 2.
  watch([title, subject, grade], () => {
    if (caseType.value !== 'teaching_design' || !uploadedFile.value) return
    if (!teachingCopyStream) return
    const next = currentTeachingCopyFingerprint()
    if (!next || next === teachingCopyStream.fingerprint) return
    if (metadataRestartTimer) {
      clearTimeout(metadataRestartTimer)
    }
    metadataRestartTimer = setTimeout(() => {
      metadataRestartTimer = null
      if (caseType.value !== 'teaching_design' || !uploadedFile.value) return
      const onStep2 = options.step == null || options.step.value === 2
      const latest = currentTeachingCopyFingerprint()
      if (!latest) return
      if (teachingCopyStream && teachingCopyStream.fingerprint === latest) return
      clearTeachingCopyPrefetch()
      if (onStep2) {
        beginTeachingCopyPrefetch({
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
    clearTeachingCopyPrefetch,
    beginTeachingCopyPrefetch,
    generateDescription,
    resetAiCopyFields,
    markDescriptionDirty,
    markDesignHighlightsDirty,
    markTeachingReflectionDirty,
  }
}
