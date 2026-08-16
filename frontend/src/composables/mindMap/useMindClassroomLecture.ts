/**
 * Mind Classroom lecture runner — walk map, caption, optional TTS.
 */
import { nextTick, onBeforeUnmount, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import {
  type MindClassroomJobDetail,
  cancelMindClassroomJob,
  enqueueMindClassroomJob,
  fetchMindClassroomJobByDiagram,
  isClassroomJobActive,
  isClassroomJobPlayable,
  pollMindClassroomJob,
} from '@/composables/mindMap/mindClassroomJobApi'
import { setPresentationDiagramEditLocked } from '@/composables/presentation/presentationDiagramEdit'
import {
  useAiContentLevelStore,
  useAuthStore,
  useDiagramStore,
  useMindClassroomStore,
  usePanelsStore,
  useSavedDiagramsStore,
} from '@/stores'
import { setMindMapCollapsedPaths } from '@/stores/diagram/mindMapCollapse'
import { collectLiveNodeIds, mapRemoteLectureSteps } from '@/utils/mindClassroomRemoteSteps'
import { lectureTtsSafetyMs, type MindClassroomLectureStep } from '@/utils/mindClassroomScript'

const FIT_MS = 900

let advanceTimer: ReturnType<typeof setTimeout> | null = null
let transitionTimer: ReturnType<typeof setTimeout> | null = null
let layoutTimer: ReturnType<typeof setTimeout> | null = null
let watchJobId: string | null = null
let watchPromise: Promise<
  { ok: true; phase: 'prepared' } | { ok: false; reason: 'empty' | 'cancelled' | 'failed' }
> | null = null

type QueueStartResult =
  { ok: true; phase: 'prepared' } | { ok: false; reason: 'empty' | 'cancelled' | 'failed' }

function clearAdvanceTimer(): void {
  if (advanceTimer !== null) {
    clearTimeout(advanceTimer)
    advanceTimer = null
  }
}

function clearTransitionTimer(): void {
  if (transitionTimer !== null) {
    clearTimeout(transitionTimer)
    transitionTimer = null
  }
}

function clearLayoutTimer(): void {
  if (layoutTimer !== null) {
    clearTimeout(layoutTimer)
    layoutTimer = null
  }
}

export function lectureSpeakGeneration(): number {
  return useMindClassroomStore().speakGeneration
}

function stopSpeech(): void {
  useMindClassroomStore().bumpSpeakGeneration()
  eventBus.emit('kitty:lecture_interrupt_requested', {})
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
}

function speakBrowserCaption(text: string, lang: string, onEnd: () => void): void {
  if (typeof window === 'undefined' || !window.speechSynthesis) {
    onEnd()
    return
  }
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
  const utter = new SpeechSynthesisUtterance(text)
  const normalizedLanguage = lang.replace('_', '-')
  utter.lang = normalizedLanguage.startsWith('zh')
    ? normalizedLanguage.toLowerCase().includes('tw')
      ? 'zh-TW'
      : 'zh-CN'
    : normalizedLanguage
  utter.rate = 1.02
  utter.onend = () => onEnd()
  utter.onerror = () => onEnd()
  window.speechSynthesis.speak(utter)
}

function speakCaption(
  text: string,
  lang: string,
  onEnd: () => void,
  stepId: string | undefined,
  preferKitty: boolean,
  prefetch?: { text: string; stepId?: string }
): void {
  const generation = lectureSpeakGeneration()
  let settled = false
  let safetyTimer: ReturnType<typeof setTimeout> | null = null
  const onKittyDone = (payload?: { fallback?: boolean; stepId?: string }): void => {
    if (generation !== lectureSpeakGeneration()) {
      eventBus.off('kitty:lecture_tts_done', onKittyDone)
      return
    }
    if (payload?.stepId && stepId && payload.stepId !== stepId) {
      return
    }
    if (payload?.fallback) {
      eventBus.off('kitty:lecture_tts_done', onKittyDone)
      speakBrowserCaption(text, lang, settle)
      return
    }
    settle()
  }
  const settle = (): void => {
    if (settled || generation !== lectureSpeakGeneration()) return
    settled = true
    if (safetyTimer !== null) {
      clearTimeout(safetyTimer)
      safetyTimer = null
    }
    eventBus.off('kitty:lecture_tts_done', onKittyDone)
    onEnd()
  }
  if (!preferKitty) {
    speakBrowserCaption(text, lang, settle)
    return
  }
  eventBus.on('kitty:lecture_tts_done', onKittyDone)
  safetyTimer = window.setTimeout(() => {
    settle()
  }, lectureTtsSafetyMs(text, 0))
  eventBus.emit('kitty:lecture_narrate_requested', {
    text,
    stepId,
    prefetchText: prefetch?.text,
    prefetchStepId: prefetch?.stepId,
    generation,
  })
}

function isTypingInInput(): boolean {
  const active = document.activeElement as HTMLElement | null
  return (
    active?.tagName === 'INPUT' ||
    active?.tagName === 'TEXTAREA' ||
    Boolean(active?.isContentEditable)
  )
}

function isInteractiveTarget(target: EventTarget | null): boolean {
  return (
    target instanceof Element &&
    Boolean(
      target.closest(
        'button, a, input, select, textarea, [contenteditable="true"], [role="option"], [role="radio"]'
      )
    )
  )
}

interface MindClassroomLectureOptions {
  bootstrap?: boolean
}

export function teardownMindClassroomLecture(options: { restoreViewport?: boolean } = {}): void {
  const classroomStore = useMindClassroomStore()
  const diagramStore = useDiagramStore()
  const collapsed = classroomStore.preLectureCollapsedPaths
  const hadLectureState = classroomStore.isLecturing || collapsed !== null

  classroomStore.bumpQueueGeneration()
  watchJobId = null
  watchPromise = null
  clearAdvanceTimer()
  clearTransitionTimer()
  clearLayoutTimer()
  stopSpeech()
  classroomStore.clearSession()
  diagramStore.clearSelection()
  setPresentationDiagramEditLocked(false)

  if (collapsed && diagramStore.data) {
    setMindMapCollapsedPaths(diagramStore.data as Record<string, unknown>, collapsed)
    diagramStore.mindMapRecalcTrigger += 1
  }
  classroomStore.setPreLectureCollapsedPaths(null)

  if (hadLectureState && options.restoreViewport !== false) {
    void nextTick(() => {
      eventBus.emit('view:viewport_snapshot_restore', {
        animate: true,
        duration: FIT_MS,
      })
    })
  }
}

export function useMindClassroomLecture(options: MindClassroomLectureOptions = {}) {
  const { t, currentLanguage } = useLanguage()
  const diagramStore = useDiagramStore()
  const classroomStore = useMindClassroomStore()
  const aiLevelStore = useAiContentLevelStore()
  const panelsStore = usePanelsStore()
  const { closeActiveTool } = useMindMapSideToolbarState()
  const savedDiagramsStore = useSavedDiagramsStore()
  const { status, stepIndex, steps, voiceEnabled, isLecturing, currentStep } =
    storeToRefs(classroomStore)

  function emitFitStep(stepIndexValue: number): void {
    const step = steps.value[stepIndexValue]
    if (!step) return
    if (step.branchNodeId) {
      diagramStore.expandMindMapPathToNode(step.branchNodeId)
    }
    if (step.branchNodeId && step.kind === 'branch') {
      diagramStore.selectNodes([step.branchNodeId])
    } else {
      diagramStore.clearSelection()
    }
    void nextTick(() => {
      eventBus.emit('view:fit_to_nodes_requested', {
        nodeIds: step.focusNodeIds,
        animate: true,
        duration: FIT_MS,
        padding:
          step.kind === 'overview' || step.kind === 'closing'
            ? 0.28
            : step.focusNodeIds.length <= 1
              ? 0.48
              : 0.36,
        userInitiated: true,
      })
    })
  }

  function advanceToNextSection(): void {
    if (status.value !== 'running') return
    if (stepIndex.value >= steps.value.length - 1) {
      stopLecture()
      return
    }
    goToStep(stepIndex.value + 1, { interruptVoice: false })
  }

  function scheduleAdvance(dwellMs: number): void {
    clearAdvanceTimer()
    if (status.value !== 'running') return
    advanceTimer = window.setTimeout(() => {
      advanceToNextSection()
    }, dwellMs)
  }

  function afterStepReady(index: number): void {
    classroomStore.transitioning = false
    const step = steps.value[index]
    if (!step || status.value !== 'running') return

    if (voiceEnabled.value) {
      let settled = false
      const settle = (): void => {
        if (settled || status.value !== 'running') return
        settled = true
        classroomStore.setNarrating(false)
        advanceToNextSection()
      }
      classroomStore.setNarrating(true)
      const preferKitty = useAuthStore().isAuthenticated
      const upcoming = steps.value[index + 1]
      const prefetch =
        upcoming?.caption.trim()
          ? { text: upcoming.caption, stepId: upcoming.id }
          : undefined
      speakCaption(step.caption, currentLanguage.value, settle, step.id, preferKitty, prefetch)
      return
    }

    classroomStore.setNarrating(false)
    scheduleAdvance(step.dwellMs)
  }

  function goToStep(index: number, options: { interruptVoice?: boolean } = {}): void {
    if (!steps.value.length) return
    const next = Math.max(0, Math.min(steps.value.length - 1, index))
    clearAdvanceTimer()
    clearTransitionTimer()
    clearLayoutTimer()
    classroomStore.setNarrating(false)
    if (options.interruptVoice === false) {
      classroomStore.bumpSpeakGeneration()
    } else {
      stopSpeech()
    }
    classroomStore.stepIndex = next
    classroomStore.transitioning = true
    emitFitStep(next)
    transitionTimer = window.setTimeout(() => afterStepReady(next), FIT_MS + 60)
  }

  function playPreparedSteps(
    nextSteps: MindClassroomLectureStep[],
    mode: typeof classroomStore.presentation
  ): { ok: true } | { ok: false; reason: 'empty' } {
    if (!nextSteps.length) return { ok: false, reason: 'empty' }
    const data = diagramStore.data
    closeActiveTool()
    classroomStore.closeModal()
    panelsStore.closeMindmate()
    panelsStore.closeNodePalette()
    setPresentationDiagramEditLocked(true)
    classroomStore.setPreLectureCollapsedPaths(
      data?._collapsed_paths ? [...data._collapsed_paths] : []
    )
    eventBus.emit('view:viewport_snapshot_save', {})
    classroomStore.beginSession(nextSteps, mode)
    void nextTick(() => {
      goToStep(0)
      if (mode === 'slide_deck') {
        layoutTimer = window.setTimeout(() => goToStep(0), 160)
      }
    })
    return { ok: true }
  }

  function jobSettingsMatch(settings: Record<string, unknown> | undefined): boolean {
    if (!settings) return false
    if (settings.mode !== classroomStore.presentation) return false
    if (settings.mastery !== classroomStore.mastery) return false
    if (settings.tone !== classroomStore.tone) return false
    if (settings.tour_scope !== classroomStore.tourScope) return false
    if (
      classroomStore.presentation === 'slide_deck' &&
      settings.slide_style !== classroomStore.slideStyle
    ) {
      return false
    }
    return settings.audience_level === aiLevelStore.level
  }

  function applyReadyDetail(detail: MindClassroomJobDetail): QueueStartResult {
    const mapped = mapRemoteLectureSteps(
      detail.result_json?.steps ?? [],
      collectLiveNodeIds(diagramStore.data?.nodes)
    )
    if (!mapped.length) return { ok: false, reason: 'empty' }
    classroomStore.setJobState({
      id: detail.id,
      status: detail.status,
      progress: detail.progress ?? null,
      error: null,
    })
    classroomStore.setPreparedSteps(mapped)
    return { ok: true, phase: 'prepared' }
  }

  function awaitJobReady(jobId: string, generation: number): Promise<QueueStartResult> {
    if (watchJobId === jobId && watchPromise) {
      return watchPromise
    }
    watchJobId = jobId
    watchPromise = (async () => {
      try {
        const detail = await pollMindClassroomJob(jobId, {
          shouldStop: () => generation !== classroomStore.queueGeneration,
          onUpdate: (next) => {
            classroomStore.setJobState({
              status: next.status,
              progress: next.progress ?? null,
              error: next.error_message ?? null,
            })
          },
        })
        if (generation !== classroomStore.queueGeneration) {
          return { ok: false, reason: 'cancelled' as const }
        }
        return applyReadyDetail(detail)
      } catch (err) {
        if (generation !== classroomStore.queueGeneration) {
          return { ok: false, reason: 'cancelled' as const }
        }
        const message = err instanceof Error ? err.message : String(err)
        if (message === 'cancelled') return { ok: false, reason: 'cancelled' as const }
        classroomStore.setJobState({ status: 'failed', error: message })
        return { ok: false, reason: 'failed' as const }
      } finally {
        if (watchJobId === jobId) {
          watchJobId = null
          watchPromise = null
        }
      }
    })()
    return watchPromise
  }

  async function restorePreparedFromServer(): Promise<boolean> {
    const authStore = useAuthStore()
    if (!authStore.isAuthenticated) return false
    const diagramId = useSavedDiagramsStore().activeDiagramId
    if (!diagramId) return false
    try {
      const detail = await fetchMindClassroomJobByDiagram(diagramId, classroomStore.presentation)
      if (!jobSettingsMatch(detail.settings)) {
        return false
      }
      if (isClassroomJobPlayable(detail.status)) {
        return applyReadyDetail(detail).ok
      }
      if (!isClassroomJobActive(detail.status)) {
        return false
      }
      classroomStore.setJobState({
        id: detail.id,
        status: detail.status,
        progress: detail.progress ?? null,
        error: detail.error_message ?? null,
      })
      void awaitJobReady(detail.id, classroomStore.queueGeneration)
      return true
    } catch {
      return false
    }
  }

  async function startQueuedLecture(reuse = true): Promise<QueueStartResult> {
    const data = diagramStore.data
    const generation = classroomStore.queueGeneration
    const mode = classroomStore.presentation
    const language = currentLanguage.value.startsWith('zh') ? 'zh' : 'en'
    const saved = useSavedDiagramsStore()
    classroomStore.setJobState({
      status: 'queued',
      progress: { phase: 'queued' },
      error: null,
    })
    try {
      const created = await enqueueMindClassroomJob({
        mode,
        spec_snapshot: {
          type: data?.type,
          nodes: data?.nodes ?? [],
          connections: data?.connections ?? [],
        },
        diagram_id: saved.activeDiagramId || undefined,
        mastery: classroomStore.mastery,
        tone: classroomStore.tone,
        tour_scope: classroomStore.tourScope,
        slide_style: classroomStore.slideStyle,
        audience_level: aiLevelStore.level,
        audience_title: t(`canvas.toolbar.professionalContent.level.${aiLevelStore.level}.title`),
        language,
        reuse,
      })
      if (generation !== classroomStore.queueGeneration) return { ok: false, reason: 'cancelled' }
      classroomStore.setJobState({ id: created.job_id, status: created.status || 'queued' })
      if (isClassroomJobPlayable(created.status)) {
        return awaitJobReady(created.job_id, generation)
      }
      if (created.status === 'failed') {
        classroomStore.setJobState({ status: 'failed', error: 'failed' })
        return { ok: false, reason: 'failed' }
      }
      return awaitJobReady(created.job_id, generation)
    } catch (err) {
      if (generation !== classroomStore.queueGeneration) return { ok: false, reason: 'cancelled' }
      const message = err instanceof Error ? err.message : String(err)
      if (message === 'cancelled') return { ok: false, reason: 'cancelled' }
      classroomStore.setJobState({ status: 'failed', error: message })
      return { ok: false, reason: 'failed' }
    }
  }

  type LectureStartResult =
    | { ok: true; phase: 'prepared' | 'playing' }
    | { ok: false; reason: 'empty' | 'no_diagram' | 'cancelled' | 'failed' | 'unauthenticated' }

  function publishQueueResult(
    action: 'start' | 'restart',
    result: LectureStartResult
  ): LectureStartResult {
    eventBus.emit('classroom:queue_result', { ...result, action })
    return result
  }

  async function startLecture(reuse = true): Promise<LectureStartResult> {
    classroomStore.setStartInFlight(true)
    try {
      const data = diagramStore.data
      if (!data?.nodes?.length) {
        return publishQueueResult('start', { ok: false, reason: 'no_diagram' })
      }
      const authStore = useAuthStore()
      if (!authStore.isAuthenticated) {
        return publishQueueResult('start', { ok: false, reason: 'unauthenticated' })
      }
      const mode = classroomStore.presentation
      if (classroomStore.preparedSteps.length) {
        const played = playPreparedSteps(classroomStore.preparedSteps, mode)
        return publishQueueResult(
          'start',
          played.ok ? { ok: true, phase: 'playing' } : played
        )
      }
      const attached = await restorePreparedFromServer()
      if (classroomStore.preparedSteps.length) {
        return publishQueueResult('start', { ok: true, phase: 'prepared' })
      }
      if (attached && classroomStore.jobId && isClassroomJobActive(classroomStore.jobStatus)) {
        return publishQueueResult(
          'start',
          await awaitJobReady(classroomStore.jobId, classroomStore.queueGeneration)
        )
      }
      return publishQueueResult('start', await startQueuedLecture(reuse))
    } finally {
      classroomStore.setStartInFlight(false)
    }
  }

  async function cancelQueuedJob(): Promise<void> {
    classroomStore.bumpQueueGeneration()
    const jobId = classroomStore.jobId
    if (jobId) {
      try {
        await cancelMindClassroomJob(jobId)
      } catch {
        /* already gone */
      }
    }
    classroomStore.clearPrepared()
  }

  async function restartLecture(): Promise<LectureStartResult> {
    classroomStore.setStartInFlight(true)
    try {
      const data = diagramStore.data
      if (!data?.nodes?.length) {
        return publishQueueResult('restart', { ok: false, reason: 'no_diagram' })
      }
      const authStore = useAuthStore()
      if (!authStore.isAuthenticated) {
        return publishQueueResult('restart', { ok: false, reason: 'unauthenticated' })
      }
      await cancelQueuedJob()
      return publishQueueResult('restart', await startQueuedLecture(false))
    } finally {
      classroomStore.setStartInFlight(false)
    }
  }

  function pauseLecture(): void {
    if (status.value !== 'running') return
    classroomStore.status = 'paused'
    clearAdvanceTimer()
    stopSpeech()
  }

  function resumeLecture(): void {
    if (status.value !== 'paused') return
    classroomStore.status = 'running'
    afterStepReady(stepIndex.value)
  }

  function togglePause(): void {
    if (status.value === 'running') pauseLecture()
    else if (status.value === 'paused') resumeLecture()
  }

  function nextStep(): void {
    if (!isLecturing.value || classroomStore.transitioning) return
    if (stepIndex.value >= steps.value.length - 1) {
      stopLecture()
      return
    }
    if (status.value === 'paused') classroomStore.status = 'running'
    goToStep(stepIndex.value + 1)
  }

  function prevStep(): void {
    if (!isLecturing.value || classroomStore.transitioning) return
    if (stepIndex.value <= 0) return
    if (status.value === 'paused') classroomStore.status = 'running'
    goToStep(stepIndex.value - 1)
  }

  function stopLecture(): void {
    teardownMindClassroomLecture()
  }

  function handleKeyboard(event: KeyboardEvent): void {
    if (!isLecturing.value) return
    if (isTypingInInput()) return
    if (isInteractiveTarget(event.target)) return
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      stopLecture()
      return
    }
    if (event.key === ' ' || event.key === 'ArrowRight' || event.key === 'PageDown') {
      event.preventDefault()
      event.stopPropagation()
      if (event.key === ' ') {
        togglePause()
      } else {
        nextStep()
      }
      return
    }
    if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
      event.preventDefault()
      event.stopPropagation()
      prevStep()
    }
  }

  function bootstrapEngine(): void {
    const owner = 'MindClassroomLectureEngine'
    eventBus.onWithOwner(
      'classroom:start_requested',
      (payload) => {
        void startLecture(payload.reuse !== false)
      },
      owner
    )
    eventBus.onWithOwner(
      'classroom:restart_requested',
      () => {
        void restartLecture()
      },
      owner
    )
    eventBus.onWithOwner(
      'classroom:stop_requested',
      (payload) => {
        teardownMindClassroomLecture({ restoreViewport: payload.restoreViewport })
      },
      owner
    )
    eventBus.onWithOwner(
      'classroom:toggle_pause_requested',
      () => {
        togglePause()
      },
      owner
    )
    eventBus.onWithOwner(
      'classroom:next_requested',
      () => {
        nextStep()
      },
      owner
    )
    eventBus.onWithOwner(
      'classroom:prev_requested',
      () => {
        prevStep()
      },
      owner
    )
    eventBus.onWithOwner(
      'classroom:set_voice_requested',
      (payload) => {
        classroomStore.setVoiceEnabled(payload.enabled)
      },
      owner
    )
    eventBus.onWithOwner(
      'classroom:restore_prepared_requested',
      () => {
        void restorePreparedFromServer()
      },
      owner
    )

    let keyboardBound = false
    watch(
      isLecturing,
      (on) => {
        if (on && !keyboardBound) {
          window.addEventListener('keydown', handleKeyboard, true)
          keyboardBound = true
        } else if (!on && keyboardBound) {
          window.removeEventListener('keydown', handleKeyboard, true)
          keyboardBound = false
        }
      },
      { immediate: true }
    )
    watch(voiceEnabled, (on) => {
      if (on) return
      stopSpeech()
      clearAdvanceTimer()
      const step = currentStep.value
      if (step && status.value === 'running') {
        scheduleAdvance(step.dwellMs)
      }
    })
    watch(
      () => savedDiagramsStore.activeDiagramId,
      (nextId, prevId) => {
        if (nextId === prevId) return
        if (prevId != null) {
          teardownMindClassroomLecture({ restoreViewport: false })
          classroomStore.closeModal()
        }
        if (nextId) eventBus.emit('classroom:restore_prepared_requested', {})
      },
      { immediate: true }
    )

    onBeforeUnmount(() => {
      eventBus.removeAllListenersForOwner(owner)
      if (keyboardBound) {
        window.removeEventListener('keydown', handleKeyboard, true)
      }
      teardownMindClassroomLecture({ restoreViewport: false })
    })
  }

  if (options.bootstrap) bootstrapEngine()

  return {
    isLecturing,
    status,
    currentStep,
    stepIndex,
    steps,
    voiceEnabled,
    startLecture,
    restartLecture,
    restorePreparedFromServer,
    cancelQueuedJob,
    stopLecture,
    pauseLecture,
    resumeLecture,
    togglePause,
    nextStep,
    prevStep,
    goToStep,
    setVoiceEnabled: classroomStore.setVoiceEnabled,
  }
}
