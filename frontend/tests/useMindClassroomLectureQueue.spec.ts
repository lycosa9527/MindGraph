import { createApp, defineComponent, h } from 'vue'

import { createPinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useMindClassroomLecture } from '@/composables/mindMap/useMindClassroomLecture'
import { useAuthStore, useDiagramStore, useMindClassroomStore } from '@/stores'
import type { DiagramData } from '@/types'

const enqueueMindClassroomJob = vi.fn()
const pollMindClassroomJob = vi.fn()
const cancelMindClassroomJob = vi.fn()

vi.mock('@/composables/mindMap/mindClassroomJobApi', () => ({
  enqueueMindClassroomJob: (...args: unknown[]) => enqueueMindClassroomJob(...args),
  pollMindClassroomJob: (...args: unknown[]) => pollMindClassroomJob(...args),
  cancelMindClassroomJob: (...args: unknown[]) => cancelMindClassroomJob(...args),
}))

vi.mock('@/composables/core/useLanguage', () => ({
  useLanguage: () => ({
    t: (key: string) => key,
    currentLanguage: { value: 'en' },
  }),
}))

vi.mock('@/composables/canvasToolbar/useMindMapSideToolbarState', () => ({
  useMindMapSideToolbarState: () => ({ closeActiveTool: vi.fn() }),
}))

vi.mock('@/composables/presentation/presentationDiagramEdit', () => ({
  setPresentationDiagramEditLocked: vi.fn(),
}))

let lecture: ReturnType<typeof useMindClassroomLecture> | null = null

const LectureProbe = defineComponent({
  setup() {
    lecture = useMindClassroomLecture({ bootstrap: false })
    return () => h('div')
  },
})

describe('useMindClassroomLecture queued start', () => {
  beforeEach(() => {
    lecture = null
    enqueueMindClassroomJob.mockReset()
    pollMindClassroomJob.mockReset()
    cancelMindClassroomJob.mockReset()
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('enqueues a classroom job, holds the transcript, then plays on the second start', async () => {
    enqueueMindClassroomJob.mockResolvedValue({ job_id: 'job-1', status: 'queued' })
    pollMindClassroomJob.mockResolvedValue({
      id: 'job-1',
      status: 'ready',
      result_json: {
        steps: [
          {
            id: 's1',
            kind: 'overview',
            title: 'Hello',
            caption: 'Welcome',
            focus_node_ids: ['topic', 'missing'],
          },
        ],
      },
    })

    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const auth = useAuthStore(pinia)
    auth.user = { id: 1, username: 'tester' } as never
    const diagram = useDiagramStore(pinia)
    diagram.data = {
      type: 'mindmap',
      nodes: [{ id: 'topic', text: 'Topic', type: 'topic', position: { x: 0, y: 0 } }],
      connections: [],
    } satisfies DiagramData

    const classroom = useMindClassroomStore(pinia)
    const prepared = await lecture?.startLecture()
    expect(prepared).toEqual({ ok: true, phase: 'prepared' })
    expect(classroom.isLecturing).toBe(false)
    expect(classroom.preparedSteps[0]?.focusNodeIds).toEqual(['topic'])
    expect(enqueueMindClassroomJob).toHaveBeenCalled()
    expect(pollMindClassroomJob).toHaveBeenCalledWith(
      'job-1',
      expect.objectContaining({ shouldStop: expect.any(Function) })
    )

    const started = await lecture?.startLecture()
    expect(started).toEqual({ ok: true, phase: 'playing' })
    expect(classroom.isLecturing).toBe(true)

    enqueueMindClassroomJob.mockClear()
    enqueueMindClassroomJob.mockResolvedValue({ job_id: 'job-2', status: 'queued' })
    pollMindClassroomJob.mockResolvedValue({
      id: 'job-2',
      status: 'ready',
      result_json: {
        steps: [
          {
            id: 's2',
            kind: 'overview',
            title: 'Again',
            caption: 'Fresh',
            focus_node_ids: ['topic'],
          },
        ],
      },
    })
    const restarted = await lecture?.restartLecture()
    expect(restarted).toEqual({ ok: true, phase: 'prepared' })
    expect(enqueueMindClassroomJob).toHaveBeenCalledWith(expect.objectContaining({ reuse: false }))
    app.unmount()
  })
})
