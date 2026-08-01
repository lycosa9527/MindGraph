import { nextTick, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const streamShowcaseTeachingCopy = vi.hoisted(() => vi.fn())

vi.mock('@/composables/showcase/generateShowcaseTeachingCopy', () => ({
  teachingCopyFingerprint: vi.fn(
    (input: { file: File; title: string; subject: string; grade: string }) =>
      `${input.file.name}|${input.title}|${input.subject}|${input.grade}`,
  ),
  streamShowcaseTeachingCopy,
}))

import { useShowcaseTeachingCopyAi } from '@/composables/showcase/useShowcaseTeachingCopyAi'

function collectUnhandledRejections(run: () => Promise<void>): Promise<unknown[]> {
  const reasons: unknown[] = []
  const onRejection = (event: PromiseRejectionEvent) => {
    reasons.push(event.reason)
    event.preventDefault()
  }
  window.addEventListener('unhandledrejection', onRejection)
  return run()
    .then(async () => {
      // Allow microtasks from fire-and-forget chains to settle.
      await new Promise((resolve) => setTimeout(resolve, 0))
      return reasons
    })
    .finally(() => {
      window.removeEventListener('unhandledrejection', onRejection)
    })
}

describe('useShowcaseTeachingCopyAi', () => {
  beforeEach(() => {
    streamShowcaseTeachingCopy.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('handles Invalid API key without unhandledrejection', async () => {
    streamShowcaseTeachingCopy.mockRejectedValue(
      new Error(
        'Invalid API key. Common causes: environment variable read error, incorrect key, region mismatch.',
      ),
    )

    const notify = {
      info: vi.fn(),
      success: vi.fn(),
      error: vi.fn(),
    }
    const file = new File(['doc'], 'lesson.pdf', { type: 'application/pdf' })

    const reasons = await collectUnhandledRejections(async () => {
      const ai = useShowcaseTeachingCopyAi({
        t: (key: string) => key,
        notify,
        caseType: ref('teaching_design'),
        title: ref('课例'),
        subject: ref('语文'),
        grade: ref('六年级'),
        uploadedFile: ref(file),
        description: ref(''),
        designHighlights: ref(''),
        step: ref(2),
      })

      ai.beginTeachingCopyPrefetch({
        notifyStart: false,
        notifySuccess: true,
        notifyError: true,
        forceOverwrite: true,
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(notify.error).toHaveBeenCalled()
      })
      expect(notify.error.mock.calls[0]?.[0]).toContain('Invalid API key')
      expect(ai.aiGeneratePhase.value).toBe('error')
    })

    expect(reasons).toEqual([])
  })

  it('swallows abort without notifying error or unhandledrejection', async () => {
    streamShowcaseTeachingCopy.mockImplementation(
      () =>
        new Promise((_resolve, reject) => {
          queueMicrotask(() => {
            reject(new DOMException('The user aborted a request.', 'AbortError'))
          })
        }),
    )

    const notify = {
      info: vi.fn(),
      success: vi.fn(),
      error: vi.fn(),
    }
    const file = new File(['doc'], 'lesson.pdf', { type: 'application/pdf' })

    const reasons = await collectUnhandledRejections(async () => {
      const ai = useShowcaseTeachingCopyAi({
        t: (key: string) => key,
        notify,
        caseType: ref('teaching_design'),
        title: ref('课例'),
        subject: ref('语文'),
        grade: ref('六年级'),
        uploadedFile: ref(file),
        description: ref(''),
        designHighlights: ref(''),
        step: ref(2),
      })

      ai.beginTeachingCopyPrefetch()
      ai.clearTeachingCopyPrefetch()
      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    expect(notify.error).not.toHaveBeenCalled()
    expect(reasons).toEqual([])
  })
})
