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
import { useAiContentLevelStore } from '@/stores/aiContentLevel'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'
import { useUIStore } from '@/stores/ui'
import { collectLiveNodeIds } from '@/utils/mindClassroomRemoteSteps'
import {
  classroomPrepSettingsOf,
  emptyMindClassroomPrep,
  parkMindClassroomPrep,
  type MindClassroomPrepSettings,
  type MindClassroomPrepSnapshot,
  type MindClassroomVoiceWarmup,
} from '@/utils/mindClassroomPrepSlot'
import {
  expandLectureFocusNodeIds,
  type MindClassroomLectureStep,
} from '@/utils/mindClassroomScript'

export type { MindClassroomVoiceWarmup } from '@/utils/mindClassroomPrepSlot'
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
  const specNodeIds = ref<string[]>([])
  const prepSettings = ref<MindClassroomPrepSettings | null>(null)
  const voiceWarmup = ref<MindClassroomVoiceWarmup>('idle')
  const startInFlight = ref(false)
  const speakGeneration = ref(0)
  const queueGeneration = ref(0)
  const preLectureCollapsedPaths = ref<string[] | null>(null)
  const activePrepKey = ref('')
  const unsavedPrepEpoch = ref(0)
  const prepByKey = ref<Record<string, MindClassroomPrepSnapshot>>({})

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

  function livePrepSettings(): MindClassroomPrepSettings {
    return classroomPrepSettingsOf({
      mode: presentation.value,
      mastery: mastery.value,
      tone: tone.value,
      tourScope: tourScope.value,
      slideStyle: slideStyle.value,
      audienceLevel: useAiContentLevelStore().level,
      language: useUIStore().language,
      llmModel: useLLMResultsStore().selectedModel,
    })
  }

  function setPreparedSteps(next: MindClassroomLectureStep[], nodeIds?: string[]): void {
    preparedSteps.value = next
    if (!next.length) {
      specNodeIds.value = []
      prepSettings.value = null
      return
    }
    specNodeIds.value = nodeIds?.length
      ? nodeIds
      : [...collectLiveNodeIds(diagramStore.data?.nodes)]
    prepSettings.value = livePrepSettings()
  }

  function setVoiceWarmup(next: MindClassroomVoiceWarmup): void {
    voiceWarmup.value = next
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

  function livePrepSnapshot(): MindClassroomPrepSnapshot {
    return {
      jobId: jobId.value,
      jobStatus: jobStatus.value,
      jobProgress: jobProgress.value,
      jobError: jobError.value,
      preparedSteps: preparedSteps.value,
      voiceWarmup: voiceWarmup.value,
      specNodeIds: specNodeIds.value,
      prepSettings: prepSettings.value,
    }
  }

  function applyPrepSnapshot(next: MindClassroomPrepSnapshot): void {
    jobId.value = next.jobId
    jobStatus.value = next.jobStatus
    jobProgress.value = next.jobProgress
    jobError.value = next.jobError
    preparedSteps.value = next.preparedSteps
    voiceWarmup.value = next.voiceWarmup
    specNodeIds.value = next.specNodeIds
    prepSettings.value = next.prepSettings
  }

  function listPreparedJobs(): Array<{ id: string; status: string | null }> {
    const rows: Array<{ id: string; status: string | null }> = []
    const seen = new Set<string>()
    const push = (id: string | null, status: string | null): void => {
      if (!id || seen.has(id)) return
      seen.add(id)
      rows.push({ id, status })
    }
    push(jobId.value, jobStatus.value)
    for (const snap of Object.values(prepByKey.value)) {
      push(snap.jobId, snap.jobStatus)
    }
    return rows
  }

  function activatePrepKey(nextKey: string): boolean {
    if (!nextKey || nextKey === activePrepKey.value) return false
    if (activePrepKey.value) {
      prepByKey.value = {
        ...prepByKey.value,
        [activePrepKey.value]: parkMindClassroomPrep(livePrepSnapshot()),
      }
    }
    activePrepKey.value = nextKey
    applyPrepSnapshot(prepByKey.value[nextKey] ?? emptyMindClassroomPrep())
    startInFlight.value = false
    return true
  }

  function clearPrepared(): void {
    applyPrepSnapshot(emptyMindClassroomPrep())
    if (!activePrepKey.value) return
    const next = { ...prepByKey.value }
    delete next[activePrepKey.value]
    prepByKey.value = next
  }

  function clearAllPrepared(): void {
    queueGeneration.value += 1
    applyPrepSnapshot(emptyMindClassroomPrep())
    prepByKey.value = {}
  }

  function endSession(): void {
    status.value = 'idle'
    activeMode.value = null
    activeTourScope.value = null
    steps.value = []
    stepIndex.value = 0
    transitioning.value = false
    narrating.value = false
  }

  function bumpUnsavedPrepEpoch(): void {
    unsavedPrepEpoch.value += 1
  }

  function clearSession(): void {
    endSession()
    clearPrepared()
    bumpUnsavedPrepEpoch()
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
    specNodeIds,
    prepSettings,
    voiceWarmup,
    startInFlight,
    speakGeneration,
    queueGeneration,
    preLectureCollapsedPaths,
    activePrepKey,
    unsavedPrepEpoch,
    activatePrepKey,
    bumpUnsavedPrepEpoch,
    livePrepSettings,
    listPreparedJobs,
    endSession,
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
    setVoiceWarmup,
    setStartInFlight,
    bumpSpeakGeneration,
    bumpQueueGeneration,
    setPreLectureCollapsedPaths,
    clearPrepared,
    clearAllPrepared,
    beginSession,
    clearSession,
  }
})
