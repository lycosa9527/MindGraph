import { createApp, defineComponent, h } from 'vue'

import { createPinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import { ClassroomJobsBusyError } from '@/composables/mindMap/mindClassroomJobApi'
import {
  teardownMindClassroomLecture,
  useMindClassroomLecture,
} from '@/composables/mindMap/useMindClassroomLecture'
import {
  useAuthStore,
  useDiagramStore,
  useLLMResultsStore,
  useMindClassroomStore,
  useSavedDiagramsStore,
} from '@/stores'
import type { DiagramData } from '@/types'

const enqueueMindClassroomJob = vi.fn()
const watchMindClassroomJob = vi.fn()
const cancelMindClassroomJob = vi.fn()
const fetchMindClassroomJob = vi.fn()
const fetchMindClassroomJobByDiagram = vi.fn()

vi.mock('@/composables/mindMap/mindClassroomJobApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/composables/mindMap/mindClassroomJobApi')>()
  return {
    ...actual,
    enqueueMindClassroomJob: (...args: unknown[]) => enqueueMindClassroomJob(...args),
    watchMindClassroomJob: (...args: unknown[]) => watchMindClassroomJob(...args),
    pollMindClassroomJob: (...args: unknown[]) => watchMindClassroomJob(...args),
    cancelMindClassroomJob: (...args: unknown[]) => cancelMindClassroomJob(...args),
    fetchMindClassroomJob: (...args: unknown[]) => fetchMindClassroomJob(...args),
    fetchMindClassroomJobByDiagram: (...args: unknown[]) => fetchMindClassroomJobByDiagram(...args),
  }
})

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

const matchingSettings = {
  mode: 'canvas_tour',
  mastery: 'first_look',
  tone: 'classroom',
  tour_scope: 'main_branch',
  slide_style: 'general',
  audience_level: 'general',
  language: 'en',
}

function readyClassroomJob(
  id: string,
  step: Record<string, unknown>,
  settings: Record<string, unknown> = matchingSettings
): Record<string, unknown> {
  return {
    id,
    status: 'ready',
    settings,
    spec_node_ids: ['topic'],
    result_json: { steps: [step] },
  }
}

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
    watchMindClassroomJob.mockReset()
    cancelMindClassroomJob.mockReset()
    fetchMindClassroomJob.mockReset()
    fetchMindClassroomJob.mockRejectedValue(new Error('no job'))
    fetchMindClassroomJobByDiagram.mockReset()
    fetchMindClassroomJobByDiagram.mockRejectedValue(new Error('no job'))
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
    watchMindClassroomJob.mockResolvedValue(
      readyClassroomJob('job-1', {
        id: 's1',
        kind: 'overview',
        title: 'Hello',
        caption: 'Welcome',
        focus_node_ids: ['topic', 'missing'],
      })
    )

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
    const emitSpy = vi.spyOn(eventBus, 'emit')
    const prepared = await lecture?.startLecture()
    expect(prepared).toEqual({ ok: true, phase: 'prepared' })
    expect(classroom.isLecturing).toBe(false)
    expect(classroom.preparedSteps[0]?.focusNodeIds).toEqual(['topic'])
    expect(emitSpy).toHaveBeenCalledWith('kitty:lecture_prefetch_requested', {
      text: 'Welcome',
      stepId: 's1',
    })
    emitSpy.mockRestore()
    expect(enqueueMindClassroomJob).toHaveBeenCalled()
    expect(watchMindClassroomJob).toHaveBeenCalledWith(
      'job-1',
      expect.objectContaining({ shouldStop: expect.any(Function) })
    )

    const started = await lecture?.startLecture()
    expect(started).toEqual({ ok: true, phase: 'playing' })
    expect(classroom.isLecturing).toBe(true)

    enqueueMindClassroomJob.mockClear()
    enqueueMindClassroomJob.mockResolvedValue({ job_id: 'job-2', status: 'queued' })
    watchMindClassroomJob.mockResolvedValue(
      readyClassroomJob('job-2', {
        id: 's2',
        kind: 'overview',
        title: 'Again',
        caption: 'Fresh',
        focus_node_ids: ['topic'],
      })
    )
    const restarted = await lecture?.restartLecture()
    expect(restarted).toEqual({ ok: true, phase: 'prepared' })
    expect(enqueueMindClassroomJob).toHaveBeenCalledWith(expect.objectContaining({ reuse: false }))
    app.unmount()
  })

  it('starts first-slide TTS when the first branch lands mid-job', async () => {
    enqueueMindClassroomJob.mockResolvedValue({ job_id: 'job-early', status: 'queued' })
    let finishWatch: ((value: unknown) => void) | null = null
    watchMindClassroomJob.mockImplementation(
      (_jobId: string, options?: { onUpdate?: (detail: Record<string, unknown>) => void }) =>
        new Promise((resolve) => {
          finishWatch = resolve
          queueMicrotask(() => {
            options?.onUpdate?.({
              id: 'job-early',
              status: 'generating',
              progress: { phase: 'first_branch', tts_ready: true, done: 1, in_flight: 2 },
              result_json: {
                steps: [
                  {
                    id: 'overview-0',
                    kind: 'overview',
                    title: 'Open',
                    caption: 'Welcome',
                    focus_node_ids: ['topic'],
                  },
                ],
                partial: true,
              },
            })
          })
        })
    )

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
    const emitSpy = vi.spyOn(eventBus, 'emit')
    const pending = lecture?.startLecture()
    await vi.waitFor(() => {
      expect(emitSpy).toHaveBeenCalledWith('kitty:lecture_prefetch_requested', {
        text: 'Welcome',
        stepId: 'overview-0',
      })
    })
    expect(classroom.voiceWarmup).toBe('loading')
    expect(classroom.preparedSteps[0]?.id).toBe('overview-0')
    expect(classroom.jobStatus).toBe('generating')

    finishWatch?.(
      readyClassroomJob('job-early', {
        id: 'overview-0',
        kind: 'overview',
        title: 'Open',
        caption: 'Welcome',
        focus_node_ids: ['topic'],
      })
    )
    expect(await pending).toEqual({ ok: true, phase: 'prepared' })
    emitSpy.mockRestore()
    app.unmount()
  })

  it('keeps the first-branch warmup when ready snapshot ids drifted', async () => {
    enqueueMindClassroomJob.mockResolvedValue({ job_id: 'job-drift', status: 'queued' })
    watchMindClassroomJob.mockResolvedValue({
      ...readyClassroomJob('job-drift', {
        id: 'overview-0',
        kind: 'overview',
        title: 'Open',
        caption: 'Welcome',
        focus_node_ids: ['topic'],
      }),
      spec_node_ids: ['stale-a', 'stale-b', 'stale-c'],
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
    const started = await lecture?.startLecture()
    expect(started).toEqual({ ok: true, phase: 'prepared' })
    expect(classroom.preparedSteps[0]?.id).toBe('overview-0')
    expect(classroom.jobStatus).toBe('ready')
    app.unmount()
  })

  it('reattaches a ready row when the SSE watch drops at terminal', async () => {
    enqueueMindClassroomJob.mockResolvedValue({ job_id: 'job-drop', status: 'queued' })
    watchMindClassroomJob.mockRejectedValue(new Error('stream_unavailable'))
    fetchMindClassroomJob.mockResolvedValue(
      readyClassroomJob('job-drop', {
        id: 'overview-0',
        kind: 'overview',
        title: 'Open',
        caption: 'Welcome',
        focus_node_ids: ['topic'],
      })
    )

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
    const started = await lecture?.startLecture()
    expect(started).toEqual({ ok: true, phase: 'prepared' })
    expect(classroom.preparedSteps[0]?.id).toBe('overview-0')
    expect(fetchMindClassroomJob).toHaveBeenCalledWith('job-drop')
    app.unmount()
  })

  it('abandons an in-flight queue when the canvas session tears down', async () => {
    let finishPoll: ((value: unknown) => void) | null = null
    enqueueMindClassroomJob.mockResolvedValue({ job_id: 'job-stale', status: 'queued' })
    watchMindClassroomJob.mockImplementation(
      () =>
        new Promise((resolve) => {
          finishPoll = resolve
        })
    )

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
    const pending = lecture?.startLecture()
    await vi.waitFor(() => {
      expect(watchMindClassroomJob).toHaveBeenCalled()
    })
    teardownMindClassroomLecture({ restoreViewport: false })
    finishPoll?.({
      id: 'job-stale',
      status: 'ready',
      result_json: {
        steps: [
          { id: 'late', kind: 'overview', title: 'Late', caption: 'Nope', focus_node_ids: [] },
        ],
      },
    })
    expect(await pending).toEqual({ ok: false, reason: 'cancelled' })
    expect(classroom.preparedSteps).toEqual([])
    expect(classroom.isLecturing).toBe(false)
    app.unmount()
  })

  it('reattaches a queued server job after the modal is closed so start is ready later', async () => {
    fetchMindClassroomJobByDiagram.mockResolvedValue({
      id: 'job-keep',
      status: 'queued',
      settings: matchingSettings,
      spec_node_ids: ['topic'],
      progress: { phase: 'queued' },
    })
    let finishPoll: ((value: unknown) => void) | null = null
    watchMindClassroomJob.mockImplementation(
      () =>
        new Promise((resolve) => {
          finishPoll = resolve
        })
    )

    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const auth = useAuthStore(pinia)
    auth.user = { id: 1, username: 'tester' } as never
    const saved = useSavedDiagramsStore(pinia)
    saved.setActiveDiagram('diagram-keep')
    const diagram = useDiagramStore(pinia)
    diagram.data = {
      type: 'mindmap',
      nodes: [{ id: 'topic', text: 'Topic', type: 'topic', position: { x: 0, y: 0 } }],
      connections: [],
    } satisfies DiagramData

    const classroom = useMindClassroomStore(pinia)
    classroom.closeModal()
    const attached = await lecture?.restorePreparedFromServer()
    expect(attached).toBe(true)
    expect(classroom.jobId).toBe('job-keep')
    expect(classroom.jobStatus).toBe('queued')
    expect(enqueueMindClassroomJob).not.toHaveBeenCalled()

    finishPoll?.(
      readyClassroomJob('job-keep', {
        id: 'kept',
        kind: 'overview',
        title: 'Kept',
        caption: 'Still here',
        focus_node_ids: ['topic'],
      })
    )
    await vi.waitFor(() => {
      expect(classroom.preparedSteps[0]?.id).toBe('kept')
    })
    expect(classroom.jobStatus).toBe('ready')

    const started = await lecture?.startLecture()
    expect(started).toEqual({ ok: true, phase: 'playing' })
    expect(enqueueMindClassroomJob).not.toHaveBeenCalled()
    app.unmount()
  })

  it('starts fresh when Kitty replaced every snapshot node id', async () => {
    fetchMindClassroomJobByDiagram.mockRejectedValue(new Error('HTTP 404'))
    enqueueMindClassroomJob.mockResolvedValue({ job_id: 'job-new', status: 'queued' })
    watchMindClassroomJob.mockResolvedValue({
      ...readyClassroomJob('job-new', {
        id: 's1',
        kind: 'overview',
        title: 'Hello',
        caption: 'Welcome',
        focus_node_ids: ['new-root'],
      }),
      spec_node_ids: ['new-root'],
    })

    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const auth = useAuthStore(pinia)
    auth.user = { id: 1, username: 'tester' } as never
    const saved = useSavedDiagramsStore(pinia)
    saved.setActiveDiagram('diagram-pillow')
    const diagram = useDiagramStore(pinia)
    diagram.data = {
      type: 'mindmap',
      nodes: [{ id: 'new-root', text: '枕头', type: 'topic', position: { x: 0, y: 0 } }],
      connections: [],
    } satisfies DiagramData

    const classroom = useMindClassroomStore(pinia)
    classroom.setPreparedSteps(
      [
        {
          id: 'overview-0',
          kind: 'overview',
          title: 'Open',
          caption: 'Welcome',
          bullets: [],
          focusNodeIds: ['old-a'],
          dwellMs: 1000,
          themeIndex: 0,
        },
      ],
      ['old-a', 'old-b']
    )

    const started = await lecture?.startLecture()
    expect(started).toEqual({ ok: true, phase: 'prepared' })
    expect(classroom.isLecturing).toBe(false)
    expect(enqueueMindClassroomJob).toHaveBeenCalled()
    expect(classroom.preparedSteps[0]?.focusNodeIds).toEqual(['new-root'])
    app.unmount()
  })

  it('does not restore a ready job whose snapshot no longer fits the canvas', async () => {
    fetchMindClassroomJobByDiagram.mockResolvedValue({
      id: 'job-old',
      status: 'ready',
      settings: matchingSettings,
      spec_node_ids: ['old-a', 'old-b'],
      result_json: {
        steps: [{ id: 's1', kind: 'overview', caption: 'Hi', focus_node_ids: ['old-a'] }],
      },
    })

    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const auth = useAuthStore(pinia)
    auth.user = { id: 1, username: 'tester' } as never
    const saved = useSavedDiagramsStore(pinia)
    saved.setActiveDiagram('diagram-pillow')
    const diagram = useDiagramStore(pinia)
    diagram.data = {
      type: 'mindmap',
      nodes: [{ id: 'new-root', text: '枕头', type: 'topic', position: { x: 0, y: 0 } }],
      connections: [],
    } satisfies DiagramData

    const classroom = useMindClassroomStore(pinia)
    const attached = await lecture?.restorePreparedFromServer()
    expect(attached).toBe(false)
    expect(classroom.preparedSteps).toEqual([])
    app.unmount()
  })

  it('reattaches a generating job even when Kitty replaced live node ids', async () => {
    fetchMindClassroomJobByDiagram.mockResolvedValue({
      id: 'job-live',
      status: 'generating',
      settings: { ...matchingSettings, llm_model: 'deepseek' },
      spec_node_ids: ['old-a', 'old-b'],
      progress: { phase: 'script_parallel' },
    })
    watchMindClassroomJob.mockImplementation(() => new Promise(() => undefined))

    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const auth = useAuthStore(pinia)
    auth.user = { id: 1, username: 'tester' } as never
    const saved = useSavedDiagramsStore(pinia)
    saved.setActiveDiagram('diagram-pillow')
    const llm = useLLMResultsStore(pinia)
    llm.setSelectedModel('deepseek')
    const diagram = useDiagramStore(pinia)
    diagram.data = {
      type: 'mindmap',
      nodes: [{ id: 'new-root', text: '枕头', type: 'topic', position: { x: 0, y: 0 } }],
      connections: [],
    } satisfies DiagramData

    const classroom = useMindClassroomStore(pinia)
    const attached = await lecture?.restorePreparedFromServer()
    expect(attached).toBe(true)
    expect(classroom.jobId).toBe('job-live')
    expect(classroom.jobStatus).toBe('generating')
    expect(enqueueMindClassroomJob).not.toHaveBeenCalled()
    app.unmount()
  })

  it('does not attach another map job when the per-user cap returns 429', async () => {
    enqueueMindClassroomJob.mockRejectedValue(
      new ClassroomJobsBusyError('Too many active classroom jobs (1/1). Wait or cancel.', 'job-busy')
    )
    fetchMindClassroomJobByDiagram.mockRejectedValue(new Error('HTTP 404'))

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
    const started = await lecture?.startLecture()
    expect(started).toEqual({ ok: false, reason: 'failed' })
    expect(classroom.jobStatus).toBeNull()
    expect(classroom.preparedSteps).toEqual([])
    expect(watchMindClassroomJob).not.toHaveBeenCalled()
    app.unmount()
  })

  it('does not restore another LLM diagram job onto the current map', async () => {
    fetchMindClassroomJobByDiagram.mockResolvedValue({
      id: 'job-qwen',
      status: 'ready',
      settings: {
        mode: 'canvas_tour',
        mastery: 'first_look',
        tone: 'classroom',
        tour_scope: 'main_branch',
        slide_style: 'general',
        audience_level: 'general',
        llm_model: 'qwen',
      },
      result_json: {
        steps: [
          { id: 'qwen-s1', kind: 'overview', title: 'Qwen', caption: 'Hi', focus_node_ids: ['topic'] },
        ],
      },
    })

    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const auth = useAuthStore(pinia)
    auth.user = { id: 1, username: 'tester' } as never
    const saved = useSavedDiagramsStore(pinia)
    saved.setActiveDiagram('diagram-multi')
    const llm = useLLMResultsStore(pinia)
    llm.setSelectedModel('deepseek')
    const diagram = useDiagramStore(pinia)
    diagram.data = {
      type: 'mindmap',
      nodes: [{ id: 'topic', text: 'Topic', type: 'topic', position: { x: 0, y: 0 } }],
      connections: [],
    } satisfies DiagramData

    const classroom = useMindClassroomStore(pinia)
    const attached = await lecture?.restorePreparedFromServer()
    expect(attached).toBe(false)
    expect(classroom.preparedSteps).toEqual([])
    expect(classroom.jobId).toBeNull()
    expect(fetchMindClassroomJobByDiagram).toHaveBeenCalledWith(
      'diagram-multi',
      'canvas_tour',
      'deepseek'
    )
    app.unmount()
  })

  it('discards a restore that finishes after the user switches LLM maps', async () => {
    let finishRestore: ((detail: Record<string, unknown>) => void) | undefined
    fetchMindClassroomJobByDiagram.mockImplementation(
      () =>
        new Promise((resolve) => {
          finishRestore = resolve
        })
    )

    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const auth = useAuthStore(pinia)
    auth.user = { id: 1, username: 'tester' } as never
    const saved = useSavedDiagramsStore(pinia)
    saved.setActiveDiagram('diagram-multi')
    const llm = useLLMResultsStore(pinia)
    llm.setSelectedModel('deepseek')
    const diagram = useDiagramStore(pinia)
    diagram.data = {
      type: 'mindmap',
      nodes: [{ id: 'topic', text: 'Topic', type: 'topic', position: { x: 0, y: 0 } }],
      connections: [],
    } satisfies DiagramData

    const classroom = useMindClassroomStore(pinia)
    const pending = lecture?.restorePreparedFromServer()
    classroom.bumpQueueGeneration()
    finishRestore?.({
      id: 'job-stale',
      status: 'ready',
      settings: {
        mode: 'canvas_tour',
        mastery: 'first_look',
        tone: 'classroom',
        tour_scope: 'main_branch',
        slide_style: 'general',
        audience_level: 'general',
        llm_model: 'deepseek',
      },
      result_json: {
        steps: [
          { id: 'stale', kind: 'overview', title: 'Stale', caption: 'Hi', focus_node_ids: ['topic'] },
        ],
      },
    })
    expect(await pending).toBe(false)
    expect(classroom.preparedSteps).toEqual([])
    expect(classroom.jobId).toBeNull()
    app.unmount()
  })

  it('does not play a parked script after the audience or tone changes', async () => {
    enqueueMindClassroomJob.mockResolvedValue({ job_id: 'job-fresh', status: 'queued' })
    watchMindClassroomJob.mockResolvedValue(
      readyClassroomJob(
        'job-fresh',
        {
          id: 'fresh',
          kind: 'overview',
          title: 'Fresh',
          caption: 'New tone',
          focus_node_ids: ['topic'],
        },
        { ...matchingSettings, tone: 'story' }
      )
    )

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
    classroom.setPreparedSteps(
      [
        {
          id: 'old',
          kind: 'overview',
          title: 'Old',
          caption: 'Stale tone',
          bullets: [],
          focusNodeIds: ['topic'],
          dwellMs: 1000,
          themeIndex: 0,
        },
      ],
      ['topic']
    )
    expect(classroom.prepSettings?.tone).toBe('classroom')
    classroom.setTone('story')

    const started = await lecture?.startLecture()
    expect(started).toEqual({ ok: true, phase: 'prepared' })
    expect(classroom.isLecturing).toBe(false)
    expect(classroom.preparedSteps[0]?.id).toBe('fresh')
    expect(enqueueMindClassroomJob).toHaveBeenCalled()
    app.unmount()
  })
})
