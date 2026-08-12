import { createApp, defineComponent, h, nextTick, ref } from 'vue'

import { createPinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useMindClassroomLecture } from '@/composables/mindMap/useMindClassroomLecture'
import { useMindClassroomStore } from '@/stores'
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

describe('useMindClassroomLecture lifecycle', () => {
  beforeEach(() => {
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

  it('switches from TTS safety timing to deterministic dwell timing when muted', async () => {
    const pinia = createPinia()
    let lecture: ReturnType<typeof useMindClassroomLecture> | null = null
    const Probe = defineComponent({
      setup() {
        lecture = useMindClassroomLecture({ bootstrap: true })
        return () => h('div')
      },
    })
    const app = createApp(Probe)
    app.use(pinia)
    app.mount(document.createElement('div'))

    const classroom = useMindClassroomStore(pinia)
    classroom.beginSession(steps, 'canvas_tour')
    lecture?.goToStep(0)
    await vi.advanceTimersByTimeAsync(960)

    lecture?.setVoiceEnabled(false)
    await nextTick()
    await vi.advanceTimersByTimeAsync(2_999)
    expect(classroom.stepIndex).toBe(0)

    await vi.advanceTimersByTimeAsync(1)
    expect(classroom.stepIndex).toBe(1)

    app.unmount()
    expect(classroom.status).toBe('idle')
  })
})
