import { nextTick, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const streamShowcaseDiagramCopy = vi.hoisted(() => vi.fn())

vi.mock('@/composables/showcase/generateShowcaseDiagramCopy', () => ({
  diagramCopyFingerprint: vi.fn(
    (input: {
      specs: Record<string, unknown>[]
      title: string
      subject: string
      grade: string
      diagramType: string
    }) =>
      `${input.diagramType}|${input.title}|${input.subject}|${input.grade}|${input.specs.length}`,
  ),
  streamShowcaseDiagramCopy,
}))

import { useShowcaseDiagramCopyAi } from '@/composables/showcase/useShowcaseDiagramCopyAi'

function collectUnhandledRejections(run: () => Promise<void>): Promise<unknown[]> {
  const reasons: unknown[] = []
  const onRejection = (event: PromiseRejectionEvent) => {
    reasons.push(event.reason)
    event.preventDefault()
  }
  window.addEventListener('unhandledrejection', onRejection)
  return run()
    .then(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0))
      return reasons
    })
    .finally(() => {
      window.removeEventListener('unhandledrejection', onRejection)
    })
}

describe('useShowcaseDiagramCopyAi', () => {
  beforeEach(() => {
    streamShowcaseDiagramCopy.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('handles stream failure without unhandledrejection', async () => {
    streamShowcaseDiagramCopy.mockRejectedValue(new Error('AI generation failed'))

    const notify = {
      info: vi.fn(),
      success: vi.fn(),
      error: vi.fn(),
    }

    const reasons = await collectUnhandledRejections(async () => {
      const ai = useShowcaseDiagramCopyAi({
        t: (key: string) => key,
        notify,
        caseType: ref('diagram_case'),
        title: ref('课例'),
        subject: ref('科学'),
        grade: ref('六年级'),
        description: ref(''),
        classroomApplication: ref(''),
        resolveSpecSource: () => ({
          specs: [{ nodes: [{ id: '1', text: '主题' }] }],
          diagramType: 'mind_map',
        }),
        step: ref(2),
      })

      ai.beginDiagramCopyPrefetch({
        notifyStart: false,
        notifySuccess: true,
        notifyError: true,
        forceOverwrite: true,
      })

      await nextTick()
      await vi.waitFor(() => {
        expect(notify.error).toHaveBeenCalled()
      })
    })

    expect(reasons).toEqual([])
  })

  it('fills description and classroom application on success', async () => {
    streamShowcaseDiagramCopy.mockImplementation(
      async (
        _input: unknown,
        handlers: {
          onFields?: (fields: {
            description?: string
            classroomApplication?: string
          }) => void
          onDone?: (result: {
            description: string
            classroomApplication: string
            model: string
          }) => void
        },
      ) => {
        handlers.onFields?.({
          description: '图示简介',
          classroomApplication: '课堂应用',
        })
        const result = {
          description: '图示简介',
          classroomApplication: '课堂应用',
          model: 'qwen3.7-flash',
        }
        handlers.onDone?.(result)
        return result
      },
    )

    const notify = {
      info: vi.fn(),
      success: vi.fn(),
      error: vi.fn(),
    }
    const description = ref('')
    const classroomApplication = ref('')

    const ai = useShowcaseDiagramCopyAi({
      t: (key: string) => key,
      notify,
      caseType: ref('diagram_template'),
      title: ref('课例'),
      subject: ref('科学'),
      grade: ref('六年级'),
      description,
      classroomApplication,
      resolveSpecSource: () => ({
        specs: [{ topic: '主题', branches: [] }],
        diagramType: 'mind_map',
      }),
      step: ref(2),
    })

    ai.beginDiagramCopyPrefetch({
      notifyStart: false,
      notifySuccess: true,
      notifyError: true,
      forceOverwrite: true,
    })

    await vi.waitFor(() => {
      expect(description.value).toBe('图示简介')
      expect(classroomApplication.value).toBe('课堂应用')
      expect(notify.success).toHaveBeenCalled()
    })
  })
})
