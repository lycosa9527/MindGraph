/**
 * Auto-stream Showcase diagram AI copy into form fields.
 *
 * Streams into description + classroom application. Specs use JSON extract;
 * gallery images use Qwen OCR multipart. Step 2 can auto-start; button click
 * while in-flight aborts; idle click clears AI fields and regenerates.
 */
import { type Ref, ref, watch } from 'vue'

import {
  diagramCopyFingerprint,
  diagramCopyImagesFingerprint,
  streamShowcaseDiagramCopy,
  streamShowcaseDiagramCopyFromImages,
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
  images?: File[]
  /** Stable keys for edit-mode existing gallery images (path/filename). */
  existingImageKeys?: string[]
  diagramType: string
}

type PrefetchOptions = {
  notifyStart?: boolean
  notifySuccess?: boolean
  notifyError?: boolean
  forceOverwrite?: boolean
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
  resolveImageFiles?: () => Promise<File[]>
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
    if (!source) return null
    if (source.specs.length > 0) {
      return diagramCopyFingerprint({
        specs: source.specs,
        title: title.value,
        subject: subject.value,
        grade: grade.value,
        diagramType: source.diagramType,
      })
    }
    const draftImages = source.images ?? []
    const existingKeys = source.existingImageKeys ?? []
    if (draftImages.length > 0 || existingKeys.length > 0) {
      const draftPart = draftImages
        .map((file) => `${file.name}:${file.size}:${file.lastModified}`)
        .join(',')
      return [
        diagramCopyImagesFingerprint({
          images: draftImages,
          title: title.value,
          subject: subject.value,
          grade: grade.value,
          diagramType: source.diagramType,
        }),
        existingKeys.join(','),
        draftPart,
      ].join('|')
    }
    return null
  }

  function attachStreamHandlers(
    state: DiagramCopyStreamState,
    fingerprint: string,
    forceOverwrite: boolean,
    streamPromise: Promise<ShowcaseDiagramCopyResult>,
  ): void {
    state.promise = streamPromise
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
        if (state.abort.signal.aborted) {
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

  function startStreamState(
    fingerprint: string,
    prefetchOptions: PrefetchOptions | undefined,
  ): DiagramCopyStreamState {
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

    const state: DiagramCopyStreamState = {
      fingerprint,
      promise: undefined as unknown as Promise<ShowcaseDiagramCopyResult | void>,
      result: null,
      error: null,
      abort,
      phaseTimer,
      forceOverwrite: prefetchOptions?.forceOverwrite === true,
      emptyAtStart: {
        description: !options.description.value.trim(),
        classroomApplication: !options.classroomApplication.value.trim(),
      },
      notifySuccess: prefetchOptions?.notifySuccess !== false,
      notifyError: prefetchOptions?.notifyError !== false,
    }
    diagramCopyStream = state
    return state
  }

  function streamHandlers(fingerprint: string, state: DiagramCopyStreamState) {
    return {
      onPhase: (phase: 'extracting' | 'generating') => {
        if (diagramCopyStream?.fingerprint !== fingerprint) return
        if (phase === 'extracting' || phase === 'generating') {
          if (aiGeneratePhase.value === 'sending' || aiGeneratePhase.value === 'idle') {
            aiGeneratePhase.value = 'waiting'
          }
        }
      },
      onFields: (fields: ShowcaseDiagramCopyFields) => {
        if (diagramCopyStream?.fingerprint !== fingerprint) return
        if (aiGeneratePhase.value !== 'streaming') {
          aiGeneratePhase.value = 'streaming'
        }
        applyStreamFields(fields, state)
      },
      onDone: (result: ShowcaseDiagramCopyResult) => {
        if (diagramCopyStream?.fingerprint !== fingerprint) return
        diagramCopyStream.result = result
        diagramCopyStream.error = null
        applyFinalResult(result, state.forceOverwrite)
        aiGeneratePhase.value = 'streaming'
      },
    }
  }

  function beginSpecsStream(
    source: DiagramCopySpecSource,
    prefetchOptions?: PrefetchOptions,
  ): void {
    const fingerprint = diagramCopyFingerprint({
      specs: source.specs,
      title: title.value,
      subject: subject.value,
      grade: grade.value,
      diagramType: source.diagramType,
    })
    const forceOverwrite = prefetchOptions?.forceOverwrite === true
    if (
      diagramCopyStream &&
      diagramCopyStream.fingerprint === fingerprint &&
      !diagramCopyStream.error &&
      diagramCopyStream.forceOverwrite === forceOverwrite &&
      !diagramCopyStream.result
    ) {
      return
    }

    const state = startStreamState(fingerprint, prefetchOptions)
    attachStreamHandlers(
      state,
      fingerprint,
      forceOverwrite,
      streamShowcaseDiagramCopy(
        {
          specs: source.specs,
          title: title.value,
          subject: subject.value,
          grade: grade.value,
          diagramType: source.diagramType,
          signal: state.abort.signal,
        },
        streamHandlers(fingerprint, state),
      ),
    )
  }

  function beginImagesStream(
    images: File[],
    diagramTypeValue: string,
    prefetchOptions?: PrefetchOptions,
  ): void {
    const fingerprint = diagramCopyImagesFingerprint({
      images,
      title: title.value,
      subject: subject.value,
      grade: grade.value,
      diagramType: diagramTypeValue,
    })
    const forceOverwrite = prefetchOptions?.forceOverwrite === true
    if (
      diagramCopyStream &&
      diagramCopyStream.fingerprint === fingerprint &&
      !diagramCopyStream.error &&
      diagramCopyStream.forceOverwrite === forceOverwrite &&
      !diagramCopyStream.result
    ) {
      return
    }

    const state = startStreamState(fingerprint, prefetchOptions)
    attachStreamHandlers(
      state,
      fingerprint,
      forceOverwrite,
      streamShowcaseDiagramCopyFromImages(
        {
          images,
          title: title.value,
          subject: subject.value,
          grade: grade.value,
          diagramType: diagramTypeValue,
          signal: state.abort.signal,
        },
        streamHandlers(fingerprint, state),
      ),
    )
  }

  function beginDiagramCopyPrefetch(prefetchOptions?: PrefetchOptions): void {
    if (!isDiagramCaseType()) return
    const source = options.resolveSpecSource()
    if (source && source.specs.length > 0) {
      beginSpecsStream(source, prefetchOptions)
      return
    }

    const draftImages = source?.images ?? []
    const diagramTypeValue = source?.diagramType || 'mind_map'
    if (draftImages.length > 0 && !options.resolveImageFiles) {
      beginImagesStream(draftImages, diagramTypeValue, prefetchOptions)
      return
    }
    if (!options.resolveImageFiles && draftImages.length < 1) {
      return
    }

    void (async () => {
      const images =
        (await options.resolveImageFiles?.()) ??
        draftImages
      if (images.length < 1) {
        if (prefetchOptions?.notifyError !== false) {
          notify.error(String(t('showcase.publishModal.aiGenerateNeedDiagram')))
        }
        return
      }
      beginImagesStream(images, diagramTypeValue, prefetchOptions)
    })()
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
    const hasSpecs = Boolean(source && source.specs.length > 0)
    const hasImageSource = Boolean(
      (source?.images && source.images.length > 0) ||
        (source?.existingImageKeys && source.existingImageKeys.length > 0),
    )
    if (!hasSpecs && !hasImageSource) {
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
