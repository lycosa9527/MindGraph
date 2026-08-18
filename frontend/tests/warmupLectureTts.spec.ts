import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import {
  beginFirstLectureSlideWarmup,
  markLectureVoiceWarmupFailed,
  markLectureVoiceWarmupReady,
  requestFirstLectureSlidePrefetch,
  resetLectureTtsCatchup,
  tryWarmupFromJobSteps,
} from '@/composables/mindMap/warmupLectureTts'
import { useMindClassroomStore } from '@/stores/mindClassroom'
import type { MindClassroomLectureStep } from '@/utils/mindClassroomScript'

const first: MindClassroomLectureStep = {
  id: 's1',
  kind: 'overview',
  title: 'First',
  caption: 'Welcome to the map',
  bullets: [],
  focusNodeIds: [],
  dwellMs: 3_000,
  themeIndex: 0,
}

describe('warmupLectureTts', () => {
  beforeEach(() => {
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
    setActivePinia(createPinia())
  })

  afterEach(() => {
    resetLectureTtsCatchup()
    vi.unstubAllGlobals()
  })

  it('asks Kitty to buffer the first caption without playing it', () => {
    const emitSpy = vi.spyOn(eventBus, 'emit')
    requestFirstLectureSlidePrefetch([first])
    expect(emitSpy).toHaveBeenCalledWith('kitty:lecture_prefetch_requested', {
      text: 'Welcome to the map',
      stepId: 's1',
    })
    emitSpy.mockRestore()
  })

  it('skips empty captions', () => {
    const emitSpy = vi.spyOn(eventBus, 'emit')
    requestFirstLectureSlidePrefetch([])
    expect(emitSpy).not.toHaveBeenCalled()
    emitSpy.mockRestore()
  })

  it('treats classroom launch as inactive until the modal opens or a lecture starts', () => {
    const classroom = useMindClassroomStore()
    expect(classroom.isLaunchActive).toBe(false)
    classroom.openModal()
    expect(classroom.isLaunchActive).toBe(true)
    classroom.closeModal()
    classroom.setStartInFlight(true)
    expect(classroom.isLaunchActive).toBe(true)
    classroom.setStartInFlight(false)
    classroom.beginSession([first], 'canvas_tour')
    expect(classroom.isLaunchActive).toBe(true)
  })

  it('does not start TTS warmup until the classroom modal is open', () => {
    const classroom = useMindClassroomStore()
    classroom.setPreparedSteps([first])
    const emitSpy = vi.spyOn(eventBus, 'emit')
    beginFirstLectureSlideWarmup([first], true)
    expect(classroom.voiceWarmup).toBe('idle')
    expect(emitSpy).not.toHaveBeenCalledWith('kitty:lecture_prefetch_requested', {
      text: 'Welcome to the map',
      stepId: 's1',
    })
    classroom.openModal()
    beginFirstLectureSlideWarmup([first], true)
    expect(classroom.voiceWarmup).toBe('loading')
    expect(emitSpy).toHaveBeenCalledWith('kitty:lecture_prefetch_requested', {
      text: 'Welcome to the map',
      stepId: 's1',
    })
    emitSpy.mockRestore()
  })

  it('marks the start button loading voice until first-slide TTS is ready', () => {
    const classroom = useMindClassroomStore()
    classroom.openModal()
    classroom.setPreparedSteps([first])
    const emitSpy = vi.spyOn(eventBus, 'emit')
    beginFirstLectureSlideWarmup([first], true)
    expect(classroom.voiceWarmup).toBe('loading')
    expect(emitSpy).toHaveBeenCalledWith('kitty:lecture_prefetch_requested', {
      text: 'Welcome to the map',
      stepId: 's1',
    })
    markLectureVoiceWarmupReady('s1')
    expect(classroom.voiceWarmup).toBe('ready')
    expect(emitSpy).toHaveBeenCalledWith('classroom:ready', {})
    emitSpy.mockRestore()
  })

  it('does not toast ready when first-slide TTS fails', () => {
    const classroom = useMindClassroomStore()
    classroom.openModal()
    classroom.setPreparedSteps([first])
    const emitSpy = vi.spyOn(eventBus, 'emit')
    beginFirstLectureSlideWarmup([first], true)
    markLectureVoiceWarmupFailed('s1')
    expect(classroom.voiceWarmup).toBe('failed')
    expect(emitSpy).not.toHaveBeenCalledWith('classroom:ready', {})
    emitSpy.mockRestore()
  })

  it('skips voice warmup when lecture voice is off', () => {
    const classroom = useMindClassroomStore()
    classroom.openModal()
    beginFirstLectureSlideWarmup([first], false)
    expect(classroom.voiceWarmup).toBe('ready')
  })

  it('starts TTS from a partial job payload and does not re-prefetch the same slide', () => {
    const classroom = useMindClassroomStore()
    classroom.openModal()
    const emitSpy = vi.spyOn(eventBus, 'emit')
    expect(
      tryWarmupFromJobSteps(
        [{ id: 'overview-0', kind: 'overview', caption: 'Welcome to the map' }],
        new Set(),
        true
      )
    ).toBe(true)
    expect(classroom.voiceWarmup).toBe('loading')
    expect(emitSpy).toHaveBeenCalledTimes(1)
    const opening = {
      id: 'overview-0',
      kind: 'overview' as const,
      title: 'Welcome to the map',
      caption: 'Welcome to the map',
      bullets: [],
      focusNodeIds: [],
      dwellMs: 3_000,
      themeIndex: 0,
    }
    const later = {
      ...first,
      id: 'branch-1',
      kind: 'branch' as const,
      title: 'Next',
      caption: 'Later slide',
    }
    beginFirstLectureSlideWarmup([opening, later], true)
    expect(emitSpy).toHaveBeenCalledTimes(1)
    beginFirstLectureSlideWarmup([opening, later], true)
    expect(emitSpy).toHaveBeenCalledTimes(1)
    emitSpy.mockRestore()
  })

  it('prefetches again when a new map reuses the same slide id', () => {
    const emitSpy = vi.spyOn(eventBus, 'emit')
    const classroom = useMindClassroomStore()
    classroom.openModal()
    tryWarmupFromJobSteps(
      [{ id: 'overview-0', kind: 'overview', caption: 'Deepseek opening' }],
      new Set(['deepseek-a']),
      true
    )
    expect(emitSpy).toHaveBeenCalledTimes(1)
    classroom.setVoiceWarmup('idle')
    classroom.setPreparedSteps([])
    resetLectureTtsCatchup()
    tryWarmupFromJobSteps(
      [{ id: 'overview-0', kind: 'overview', caption: 'Qwen opening' }],
      new Set(['qwen-a']),
      true
    )
    expect(emitSpy).toHaveBeenCalledTimes(2)
    expect(emitSpy).toHaveBeenLastCalledWith('kitty:lecture_prefetch_requested', {
      text: 'Qwen opening',
      stepId: 'overview-0',
    })
    emitSpy.mockRestore()
  })

  it('does not prefetch later slides when a later family lands on the job', () => {
    const emitSpy = vi.spyOn(eventBus, 'emit')
    useMindClassroomStore().openModal()
    tryWarmupFromJobSteps(
      [{ id: 'overview-0', kind: 'overview', caption: 'Welcome to the map' }],
      new Set(),
      true
    )
    expect(emitSpy).toHaveBeenCalledTimes(1)
    expect(
      tryWarmupFromJobSteps(
        [
          { id: 'overview-0', kind: 'overview', caption: 'Welcome to the map' },
          { id: 'branch-1', kind: 'branch', caption: 'Second family' },
        ],
        new Set(),
        true
      )
    ).toBe(true)
    expect(emitSpy).toHaveBeenCalledTimes(1)
    expect(useMindClassroomStore().preparedSteps).toHaveLength(2)
    emitSpy.mockRestore()
  })
})
