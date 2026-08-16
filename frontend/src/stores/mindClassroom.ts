/**
 * Mind Classroom launch prefs, queue job state, and live lecture session.
 */
import { computed, ref, watch } from 'vue'

import { defineStore } from 'pinia'

import {
  DEFAULT_MIND_CLASSROOM_MASTERY,
  DEFAULT_MIND_CLASSROOM_PRESENTATION,
  DEFAULT_MIND_CLASSROOM_SLIDE_STYLE,
  DEFAULT_MIND_CLASSROOM_TONE,
  DEFAULT_MIND_CLASSROOM_TOUR_SCOPE,
  type MindClassroomMasteryId,
  type MindClassroomPresentationId,
  type MindClassroomSlideStyleId,
  type MindClassroomToneId,
  type MindClassroomTourScopeId,
  loadMindClassroomMastery,
  loadMindClassroomPresentation,
  loadMindClassroomSlideStyle,
  loadMindClassroomTone,
  loadMindClassroomTourScope,
  saveMindClassroomMastery,
  saveMindClassroomPresentation,
  saveMindClassroomSlideStyle,
  saveMindClassroomTone,
  saveMindClassroomTourScope,
} from '@/config/mindClassroom'
import { useDiagramStore } from '@/stores/diagram'
import {
  expandLectureFocusNodeIds,
  type MindClassroomLectureStep,
} from '@/utils/mindClassroomScript'

export type MindClassroomLectureStatus = 'idle' | 'running' | 'paused'

export const useMindClassroomStore = defineStore('mindClassroom', () => {
  const diagramStore = useDiagramStore()
  const mastery = ref<MindClassroomMasteryId>(loadMindClassroomMastery())
  const presentation = ref<MindClassroomPresentationId>(loadMindClassroomPresentation())
  const tourScope = ref<MindClassroomTourScopeId>(loadMindClassroomTourScope())
  const slideStyle = ref<MindClassroomSlideStyleId>(loadMindClassroomSlideStyle())
  const tone = ref<MindClassroomToneId>(loadMindClassroomTone())
  const modalOpen = ref(false)

  const status = ref<MindClassroomLectureStatus>('idle')
  const activeMode = ref<MindClassroomPresentationId | null>(null)
  const activeTourScope = ref<MindClassroomTourScopeId | null>(null)
  const steps = ref<MindClassroomLectureStep[]>([])
  const stepIndex = ref(0)
  const transitioning = ref(false)
  const narrating = ref(false)
  const voiceEnabled = ref(true)
  const jobId = ref<string | null>(null)
  const jobStatus = ref<string | null>(null)
  const jobProgress = ref<Record<string, unknown> | null>(null)
  const jobError = ref<string | null>(null)
  const preparedSteps = ref<MindClassroomLectureStep[]>([])
  const startInFlight = ref(false)
  const speakGeneration = ref(0)
  const queueGeneration = ref(0)
  const preLectureCollapsedPaths = ref<string[] | null>(null)

  watch(mastery, (value) => {
    saveMindClassroomMastery(value)
  })

  watch(presentation, (value) => {
    saveMindClassroomPresentation(value)
  })

  watch(tourScope, (value) => {
    saveMindClassroomTourScope(value)
  })

  watch(slideStyle, (value) => {
    saveMindClassroomSlideStyle(value)
  })

  watch(tone, (value) => {
    saveMindClassroomTone(value)
  })

  const isLecturing = computed(() => status.value !== 'idle')
  const isSlideDeckMode = computed(() => isLecturing.value && activeMode.value === 'slide_deck')
  const isCanvasTourMode = computed(() => isLecturing.value && activeMode.value === 'canvas_tour')
  const currentStep = computed(() => steps.value[stepIndex.value] ?? null)
  const stepCount = computed(() => steps.value.length)
  const canGoPrev = computed(() => stepIndex.value > 0)
  const canGoNext = computed(() => stepIndex.value < steps.value.length - 1)
  const progress = computed(() => {
    if (!steps.value.length) return 0
    return (stepIndex.value + 1) / steps.value.length
  })

  const sessionTourScope = computed(() => activeTourScope.value ?? tourScope.value)

  const focusNodeId = computed(() => {
    if (!isLecturing.value) return null
    const step = currentStep.value
    if (!step || step.kind !== 'branch') return null
    return step.branchNodeId ?? null
  })

  const dimFocusNodeIds = computed(() => {
    if (!isLecturing.value) return null
    const step = currentStep.value
    if (!step || step.kind === 'overview' || step.kind === 'closing') return null
    const expanded = expandLectureFocusNodeIds(
      step,
      sessionTourScope.value,
      (id) => diagramStore.getMindMapDescendantIds(id),
      activeMode.value
    )
    if (!expanded.length) return null
    return new Set(expanded)
  })

  function setMastery(next: MindClassroomMasteryId): void {
    mastery.value = next
  }

  function setPresentation(next: MindClassroomPresentationId): void {
    presentation.value = next
  }

  function setTourScope(next: MindClassroomTourScopeId): void {
    tourScope.value = next
  }

  function setSlideStyle(next: MindClassroomSlideStyleId): void {
    slideStyle.value = next
  }

  function setTone(next: MindClassroomToneId): void {
    tone.value = next
  }

  function openModal(): void {
    modalOpen.value = true
  }

  function closeModal(): void {
    modalOpen.value = false
  }

  function resetSettings(): void {
    mastery.value = DEFAULT_MIND_CLASSROOM_MASTERY
    presentation.value = DEFAULT_MIND_CLASSROOM_PRESENTATION
    tourScope.value = DEFAULT_MIND_CLASSROOM_TOUR_SCOPE
    slideStyle.value = DEFAULT_MIND_CLASSROOM_SLIDE_STYLE
    tone.value = DEFAULT_MIND_CLASSROOM_TONE
  }

  function setVoiceEnabled(next: boolean): void {
    voiceEnabled.value = next
  }

  function setNarrating(next: boolean): void {
    narrating.value = next
  }

  function beginSession(
    nextSteps: MindClassroomLectureStep[],
    mode: MindClassroomPresentationId
  ): void {
    steps.value = nextSteps
    stepIndex.value = 0
    transitioning.value = false
    narrating.value = false
    activeMode.value = mode
    activeTourScope.value = tourScope.value
    status.value = 'running'
  }

  function setJobState(next: {
    id?: string | null
    status?: string | null
    progress?: Record<string, unknown> | null
    error?: string | null
  }): void {
    if (next.id !== undefined) jobId.value = next.id
    if (next.status !== undefined) jobStatus.value = next.status
    if (next.progress !== undefined) jobProgress.value = next.progress
    if (next.error !== undefined) jobError.value = next.error
  }

  function setPreparedSteps(next: MindClassroomLectureStep[]): void {
    preparedSteps.value = next
  }

  function setStartInFlight(next: boolean): void {
    startInFlight.value = next
  }

  function bumpSpeakGeneration(): number {
    speakGeneration.value += 1
    return speakGeneration.value
  }

  function bumpQueueGeneration(): number {
    queueGeneration.value += 1
    return queueGeneration.value
  }

  function setPreLectureCollapsedPaths(next: string[] | null): void {
    preLectureCollapsedPaths.value = next
  }

  function clearPrepared(): void {
    preparedSteps.value = []
    jobId.value = null
    jobStatus.value = null
    jobProgress.value = null
    jobError.value = null
  }

  function clearSession(): void {
    status.value = 'idle'
    activeMode.value = null
    activeTourScope.value = null
    steps.value = []
    stepIndex.value = 0
    transitioning.value = false
    narrating.value = false
    clearPrepared()
  }

  return {
    mastery,
    presentation,
    tourScope,
    slideStyle,
    tone,
    modalOpen,
    status,
    activeMode,
    activeTourScope,
    sessionTourScope,
    steps,
    stepIndex,
    transitioning,
    narrating,
    voiceEnabled,
    jobId,
    jobStatus,
    jobProgress,
    jobError,
    preparedSteps,
    startInFlight,
    speakGeneration,
    queueGeneration,
    preLectureCollapsedPaths,
    isLecturing,
    isSlideDeckMode,
    isCanvasTourMode,
    currentStep,
    stepCount,
    canGoPrev,
    canGoNext,
    progress,
    focusNodeId,
    dimFocusNodeIds,
    setMastery,
    setPresentation,
    setTourScope,
    setSlideStyle,
    setTone,
    openModal,
    closeModal,
    resetSettings,
    setVoiceEnabled,
    setNarrating,
    setJobState,
    setPreparedSteps,
    setStartInFlight,
    bumpSpeakGeneration,
    bumpQueueGeneration,
    setPreLectureCollapsedPaths,
    clearPrepared,
    beginSession,
    clearSession,
  }
})
