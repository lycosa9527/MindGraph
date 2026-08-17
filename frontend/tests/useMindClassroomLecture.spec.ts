import { createApp, defineComponent, h, nextTick, ref } from 'vue'

import { createPinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import { useMindClassroomLecture } from '@/composables/mindMap/useMindClassroomLecture'
import { useAuthStore, useDiagramStore, useMindClassroomStore, useSavedDiagramsStore } from '@/stores'
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
    kind: 'closing',
    title: 'Second',
    caption: 'Second caption',
    bullets: [],
    focusNodeIds: [],
    dwellMs: 3_000,
    themeIndex: 1,
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
})
