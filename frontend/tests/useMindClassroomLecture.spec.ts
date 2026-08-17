import { createApp, defineComponent, h, nextTick, ref } from 'vue'

import { createPinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import { useMindClassroomLecture } from '@/composables/mindMap/useMindClassroomLecture'
import {
  useAuthStore,
  useDiagramStore,
  useLLMResultsStore,
  useMindClassroomStore,
  useSavedDiagramsStore,
} from '@/stores'
import type { DiagramData } from '@/types'
import type { MindClassroomLectureStep } from '@/utils/mindClassroomScript'

vi.mock('@/composables/core/useLanguage', () => ({
  useLanguage: () => ({
    t: (key: string) => key,
    currentLanguage: ref('en'),
  }),
}))

vi.mock('@/composables/canvasToolbar/useMindMapSideToolbarState', () => ({
  useMindMapSideToolbarState: () => ({ closeActiveTool: vi.fn() }),
}))

vi.mock('@/composables/presentation/presentationDiagramEdit', () => ({
  setPresentationDiagramEditLocked: vi.fn(),
}))

const steps: MindClassroomLectureStep[] = [
  {
    id: 'first',
    kind: 'overview',
    title: 'First',
    caption: 'First caption',
    bullets: [],
    focusNodeIds: [],
    dwellMs: 3_000,
    themeIndex: 0,
  },
  {
    id: 'second',
    kind: 'branch',
    title: 'Second',
    caption: 'Second caption',
    bullets: [],
    focusNodeIds: [],
    dwellMs: 3_000,
    themeIndex: 1,
  },
  {
    id: 'third',
    kind: 'closing',
    title: 'Third',
    caption: 'Third caption',
    bullets: [],
    focusNodeIds: [],
    dwellMs: 3_000,
    themeIndex: 2,
  },
]

let lecture: ReturnType<typeof useMindClassroomLecture> | null = null

const LectureProbe = defineComponent({
  setup() {
    lecture = useMindClassroomLecture({ bootstrap: true })
    return () => h('button', { id: 'lecture-control' }, 'Control')
  },
})

describe('useMindClassroomLecture lifecycle', () => {
  beforeEach(() => {
    lecture = null
    vi.useFakeTimers()
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
    vi.stubGlobal(
      'SpeechSynthesisUtterance',
      class {
        lang = ''
        rate = 1
        onend: (() => void) | null = null
        onerror: (() => void) | null = null

        constructor(public readonly text: string) {}
      }
    )
    vi.stubGlobal('speechSynthesis', {
      speak: vi.fn(),
      cancel: vi.fn(),
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('advances only after TTS ends, then uses dwell when muted', async () => {
    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const classroom = useMindClassroomStore(pinia)
    classroom.beginSession(steps, 'canvas_tour')
    lecture?.goToStep(0)
    await vi.advanceTimersByTimeAsync(960)
    expect(classroom.stepIndex).toBe(0)

    await vi.advanceTimersByTimeAsync(30_000)
    expect(classroom.stepIndex).toBe(0)

    const spoken = vi.mocked(window.speechSynthesis.speak).mock.calls.at(-1)?.[0] as {
      onend: (() => void) | null
    }
    spoken.onend?.()
    await nextTick()
    expect(classroom.stepIndex).toBe(1)

    app.unmount()
  })

  it('does not consume lecture shortcuts from focused controls', async () => {
    const pinia = createPinia()
    const host = document.createElement('div')
    document.body.append(host)
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(host)

    const classroom = useMindClassroomStore(pinia)
    classroom.beginSession(steps, 'canvas_tour')
    await nextTick()
    const control = host.querySelector<HTMLButtonElement>('#lecture-control')
    control?.focus()
    control?.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }))

    expect(classroom.stepIndex).toBe(0)
    app.unmount()
    host.remove()
  })

  it('prefetches the next caption when Kitty TTS starts a slide', async () => {
    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const auth = useAuthStore(pinia)
    auth.user = { id: 1, username: 'tester' } as never
    const classroom = useMindClassroomStore(pinia)
    classroom.beginSession(steps, 'canvas_tour')
    const emitSpy = vi.spyOn(eventBus, 'emit')
    lecture?.goToStep(0)
    await vi.advanceTimersByTimeAsync(960)

    const narrate = emitSpy.mock.calls.find(([name]) => name === 'kitty:lecture_narrate_requested')
    expect(narrate?.[1]).toMatchObject({
      text: 'First caption',
      stepId: 'first',
      prefetchText: 'Second caption',
      prefetchStepId: 'second',
    })
    expect(typeof (narrate?.[1] as { generation?: number }).generation).toBe('number')
    emitSpy.mockRestore()
    app.unmount()
  })

  it('auto-play advances without interrupt and prefetches only the next branch', async () => {
    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const auth = useAuthStore(pinia)
    auth.user = { id: 1, username: 'tester' } as never
    const classroom = useMindClassroomStore(pinia)
    classroom.beginSession(steps, 'canvas_tour')
    const emitSpy = vi.spyOn(eventBus, 'emit')
    lecture?.goToStep(0, { interruptVoice: false })
    await vi.advanceTimersByTimeAsync(960)
    eventBus.emit('kitty:lecture_tts_done', { stepId: 'first' })
    await nextTick()
    await vi.advanceTimersByTimeAsync(960)

    expect(classroom.stepIndex).toBe(1)
    expect(emitSpy.mock.calls.some(([name]) => name === 'kitty:lecture_interrupt_requested')).toBe(
      false
    )
    const narrates = emitSpy.mock.calls.filter(([name]) => name === 'kitty:lecture_narrate_requested')
    expect(narrates[0]?.[1]).toMatchObject({
      text: 'First caption',
      stepId: 'first',
      prefetchText: 'Second caption',
      prefetchStepId: 'second',
    })
    expect(narrates[1]?.[1]).toMatchObject({
      text: 'Second caption',
      stepId: 'second',
      prefetchText: 'Third caption',
      prefetchStepId: 'third',
    })
    emitSpy.mockRestore()
    app.unmount()
  })

  it('manual next interrupts and TTS the landed branch', async () => {
    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const auth = useAuthStore(pinia)
    auth.user = { id: 1, username: 'tester' } as never
    const classroom = useMindClassroomStore(pinia)
    classroom.beginSession(steps, 'canvas_tour')
    lecture?.goToStep(0, { interruptVoice: false })
    await vi.advanceTimersByTimeAsync(960)
    const emitSpy = vi.spyOn(eventBus, 'emit')
    lecture?.nextStep()
    expect(emitSpy).toHaveBeenCalledWith('kitty:lecture_interrupt_requested', {})
    await vi.advanceTimersByTimeAsync(960)
    const narrate = emitSpy.mock.calls.find(([name]) => name === 'kitty:lecture_narrate_requested')
    expect(narrate?.[1]).toMatchObject({
      text: 'Second caption',
      stepId: 'second',
      prefetchText: 'Third caption',
      prefetchStepId: 'third',
    })
    emitSpy.mockRestore()
    app.unmount()
  })

  it('starts playback without cancelling first-slide warmup', async () => {
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
    }
    const classroom = useMindClassroomStore(pinia)
    classroom.setPreparedSteps(steps)
    const emitSpy = vi.spyOn(eventBus, 'emit')
    await lecture?.startLecture()
    expect(emitSpy).toHaveBeenCalledWith('kitty:lecture_prefetch_requested', {
      text: 'First caption',
      stepId: 'first',
    })
    expect(emitSpy.mock.calls.some(([name]) => name === 'kitty:lecture_interrupt_requested')).toBe(
      false
    )
    emitSpy.mockRestore()
    app.unmount()
  })

  it('refuses to start a lecture without login', async () => {
    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const diagram = useDiagramStore(pinia)
    diagram.data = {
      type: 'mindmap',
      nodes: [{ id: 'topic', text: 'Topic', type: 'topic', position: { x: 0, y: 0 } }],
      connections: [],
    } satisfies DiagramData

    expect(await lecture?.startLecture()).toEqual({ ok: false, reason: 'unauthenticated' })
    app.unmount()
  })

  it('plays a prepared lecture from the classroom event bus', async () => {
    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const diagram = useDiagramStore(pinia)
    diagram.data = {
      type: 'mindmap',
      nodes: [{ id: 'topic', text: 'Topic', type: 'topic', position: { x: 0, y: 0 } }],
      connections: [],
    } satisfies DiagramData
    const auth = useAuthStore(pinia)
    auth.user = { id: 1, username: 'tester' } as never
    const classroom = useMindClassroomStore(pinia)
    classroom.setPreparedSteps(steps)

    const results: unknown[] = []
    const off = eventBus.on('classroom:queue_result', (payload) => {
      results.push(payload)
    })
    eventBus.emit('classroom:start_requested', { reuse: true })
    await vi.waitFor(() => {
      expect(results).toEqual([{ ok: true, phase: 'playing', action: 'start' }])
    })
    expect(classroom.isLecturing).toBe(true)
    off()
    app.unmount()
  })

  it('restores collapsed branches when a lecture stops', async () => {
    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const diagram = useDiagramStore(pinia)
    diagram.data = {
      type: 'mindmap',
      nodes: [
        { id: 'topic', text: 'Topic', type: 'topic', position: { x: 0, y: 0 } },
        { id: 'branch', text: 'Branch', type: 'branch', position: { x: 100, y: 0 } },
      ],
      connections: [{ id: 'edge', source: 'topic', target: 'branch' }],
      _collapsed_paths: ['r/0'],
    } satisfies DiagramData

    const auth = useAuthStore(pinia)
    auth.user = { id: 1, username: 'tester' } as never
    const classroom = useMindClassroomStore(pinia)
    classroom.setPreparedSteps(steps)
    expect(await lecture?.startLecture()).toEqual({ ok: true, phase: 'playing' })
    diagram.data._collapsed_paths = []
    lecture?.stopLecture()

    expect(diagram.data._collapsed_paths).toEqual(['r/0'])
    expect(classroom.isLecturing).toBe(false)
    expect(classroom.preparedSteps).toEqual(steps)
    app.unmount()
  })

  it('stops the lecture when the active diagram session changes', async () => {
    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const saved = useSavedDiagramsStore(pinia)
    saved.setActiveDiagram('diagram-a')
    await nextTick()
    const classroom = useMindClassroomStore(pinia)
    classroom.beginSession(steps, 'canvas_tour')
    expect(classroom.isLecturing).toBe(true)

    saved.setActiveDiagram('diagram-b')
    await nextTick()
    expect(classroom.isLecturing).toBe(false)
    expect(classroom.preparedSteps).toEqual([])
    expect(classroom.modalOpen).toBe(false)
    app.unmount()
  })

  it('keeps classroom prep per LLM diagram and shows ready when switching back', async () => {
    const pinia = createPinia()
    const app = createApp(LectureProbe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const saved = useSavedDiagramsStore(pinia)
    const llm = useLLMResultsStore(pinia)
    const diagram = useDiagramStore(pinia)
    saved.setActiveDiagram('diagram-multi')
    llm.setSelectedModel('qwen')
    diagram.data = {
      type: 'mindmap',
      nodes: [{ id: 'topic', text: 'Topic', type: 'topic', position: { x: 0, y: 0 } }],
      connections: [],
    } satisfies DiagramData
    await nextTick()

    const classroom = useMindClassroomStore(pinia)
    classroom.setPreparedSteps(steps)
    classroom.setVoiceWarmup('loading')
    classroom.setJobState({ id: 'job-qwen', status: 'ready' })

    llm.setSelectedModel('deepseek')
    await nextTick()
    expect(classroom.preparedSteps).toEqual([])
    expect(classroom.voiceWarmup).toBe('idle')
    expect(classroom.jobId).toBeNull()
    expect(classroom.jobStatus).toBeNull()

    llm.setSelectedModel('qwen')
    await nextTick()
    expect(classroom.preparedSteps).toEqual(steps)
    expect(classroom.voiceWarmup).toBe('ready')
    expect(classroom.jobId).toBe('job-qwen')
    expect(classroom.jobStatus).toBe('ready')
    app.unmount()
  })
})
