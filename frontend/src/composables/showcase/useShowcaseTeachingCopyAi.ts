/**
 * Prefetch + apply Showcase teaching-design AI copy (qwen3.7-flash via API).
 */
import { type Ref, ref } from 'vue'

import {
  generateShowcaseTeachingCopy,
  teachingCopyFingerprint,
  type ShowcaseTeachingCopyResult,
} from '@/composables/showcase/generateShowcaseTeachingCopy'
import type { ModelLoadPhase } from '@/stores/llmResults'

type NotifyLike = {
  info: (message: string) => void
  success: (message: string) => void
  error: (message: string) => void
}

type TranslateFn = (key: string) => unknown

type TeachingCopyPrefetch = {
  fingerprint: string
  promise: Promise<ShowcaseTeachingCopyResult>
  result: ShowcaseTeachingCopyResult | null
  error: string | null
  abort: AbortController
  phaseTimer: ReturnType<typeof setTimeout> | null
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
}) {
  const { t, notify, caseType, title, subject, grade, uploadedFile } = options
  const isGenerating = ref(false)
  const aiGeneratePhase = ref<ModelLoadPhase>('idle')
  let teachingCopyPrefetch: TeachingCopyPrefetch | null = null

  function clearTeachingCopyPrefetch(): void {
    if (teachingCopyPrefetch?.phaseTimer) {
      clearTimeout(teachingCopyPrefetch.phaseTimer)
    }
    teachingCopyPrefetch?.abort.abort()
    teachingCopyPrefetch = null
    isGenerating.value = false
    aiGeneratePhase.value = 'idle'
  }

  function applyTeachingCopyResult(result: ShowcaseTeachingCopyResult): void {
    options.description.value = result.description
    options.designHighlights.value = result.designHighlights
    options.teachingReflection.value = result.teachingReflection
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

  function beginTeachingCopyPrefetch(prefetchOptions?: { notifyStart?: boolean }): void {
    const file = uploadedFile.value
    if (!file || caseType.value !== 'teaching_design') return
    const fingerprint = teachingCopyFingerprint({
      file,
      title: title.value,
      subject: subject.value,
      grade: grade.value,
    })
    if (
      teachingCopyPrefetch &&
      teachingCopyPrefetch.fingerprint === fingerprint &&
      !teachingCopyPrefetch.error
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

    const promise = generateShowcaseTeachingCopy({
      file,
      title: title.value,
      subject: subject.value,
      grade: grade.value,
      signal: abort.signal,
    })
      .then((result) => {
        if (teachingCopyPrefetch?.fingerprint !== fingerprint) {
          return result
        }
        teachingCopyPrefetch.result = result
        teachingCopyPrefetch.error = null
        aiGeneratePhase.value = 'streaming'
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
        if (teachingCopyPrefetch?.fingerprint === fingerprint) {
          teachingCopyPrefetch.error = message
          aiGeneratePhase.value = 'error'
        }
        throw error
      })
      .finally(() => {
        if (teachingCopyPrefetch?.fingerprint !== fingerprint) return
        if (teachingCopyPrefetch.phaseTimer) {
          clearTimeout(teachingCopyPrefetch.phaseTimer)
          teachingCopyPrefetch.phaseTimer = null
        }
        isGenerating.value = false
        if (aiGeneratePhase.value === 'streaming' || aiGeneratePhase.value === 'ready') {
          aiGeneratePhase.value = 'ready'
          setTimeout(() => {
            if (aiGeneratePhase.value === 'ready') {
              aiGeneratePhase.value = 'idle'
            }
          }, 900)
        } else if (aiGeneratePhase.value !== 'error') {
          aiGeneratePhase.value = 'idle'
        }
      })

    teachingCopyPrefetch = {
      fingerprint,
      promise,
      result: null,
      error: null,
      abort,
      phaseTimer,
    }
  }

  async function generateDescription(): Promise<void> {
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

    const fingerprint = currentTeachingCopyFingerprint()
    const cached =
      teachingCopyPrefetch &&
      fingerprint &&
      teachingCopyPrefetch.fingerprint === fingerprint
        ? teachingCopyPrefetch
        : null

    if (cached?.result) {
      aiGeneratePhase.value = 'streaming'
      applyTeachingCopyResult(cached.result)
      notify.success(String(t('showcase.publishModal.aiGenerateSuccess')))
      aiGeneratePhase.value = 'ready'
      setTimeout(() => {
        if (aiGeneratePhase.value === 'ready') aiGeneratePhase.value = 'idle'
      }, 900)
      return
    }

    if (!cached || cached.error) {
      beginTeachingCopyPrefetch({ notifyStart: true })
    } else {
      notify.info(String(t('showcase.publishModal.aiGenerating')))
      if (aiGeneratePhase.value === 'idle') {
        aiGeneratePhase.value = 'waiting'
      }
    }

    const active = teachingCopyPrefetch
    if (!active) return

    try {
      isGenerating.value = true
      const result = await active.promise
      if (active.result) {
        applyTeachingCopyResult(active.result)
      } else {
        applyTeachingCopyResult(result)
      }
      notify.success(String(t('showcase.publishModal.aiGenerateSuccess')))
    } catch (error: unknown) {
      if (active.abort.signal.aborted) return
      const message =
        active.error ||
        (error instanceof Error && error.message
          ? error.message
          : String(t('showcase.publishModal.aiGenerateFailed')))
      notify.error(message)
    } finally {
      isGenerating.value = false
    }
  }

  return {
    isGenerating,
    aiGeneratePhase,
    clearTeachingCopyPrefetch,
    beginTeachingCopyPrefetch,
    generateDescription,
  }
}
