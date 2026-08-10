/**
 * Mind Classroom lecture runner — walk map, caption, optional TTS.
 */
import { nextTick, onUnmounted, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { setPresentationDiagramEditLocked } from '@/composables/presentation/presentationDiagramEdit'
import {
  useAiContentLevelStore,
  useDiagramStore,
  useMindClassroomStore,
  usePanelsStore,
} from '@/stores'
import { buildMindClassroomLectureSteps } from '@/utils/mindClassroomScript'

const FIT_MS = 900

let advanceTimer: ReturnType<typeof setTimeout> | null = null
let transitionTimer: ReturnType<typeof setTimeout> | null = null
let keyboardBound = false
let engineBootstrapped = false

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

function stopSpeech(): void {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
}

function speakCaption(text: string, lang: string, onEnd: () => void): void {
  if (typeof window === 'undefined' || !window.speechSynthesis) {
    onEnd()
    return
  }
  stopSpeech()
  const utter = new SpeechSynthesisUtterance(text)
  utter.lang = lang.startsWith('zh') ? 'zh-CN' : 'en-US'
  utter.rate = 1.02
  utter.onend = () => onEnd()
  utter.onerror = () => onEnd()
  window.speechSynthesis.speak(utter)
}

function isTypingInInput(): boolean {
  const active = document.activeElement as HTMLElement | null
  return (
    active?.tagName === 'INPUT' ||
    active?.tagName === 'TEXTAREA' ||
    Boolean(active?.isContentEditable)
  )
}

export function useMindClassroomLecture() {
  const { t, currentLanguage } = useLanguage()
  const diagramStore = useDiagramStore()
  const classroomStore = useMindClassroomStore()
  const aiLevelStore = useAiContentLevelStore()
  const panelsStore = usePanelsStore()
  const { closeActiveTool } = useMindMapSideToolbarState()
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

  function scheduleAdvance(dwellMs: number): void {
    clearAdvanceTimer()
    if (status.value !== 'running') return
    advanceTimer = window.setTimeout(() => {
      if (status.value !== 'running') return
      if (stepIndex.value >= steps.value.length - 1) {
        stopLecture()
        return
      }
      goToStep(stepIndex.value + 1)
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
        clearAdvanceTimer()
        scheduleAdvance(850)
      }
      speakCaption(step.caption, currentLanguage.value, settle)
      // Safety if browser TTS never fires end
      advanceTimer = window.setTimeout(settle, step.dwellMs + 5000)
      return
    }

    scheduleAdvance(step.dwellMs)
  }

  function goToStep(index: number): void {
    if (!steps.value.length) return
    const next = Math.max(0, Math.min(steps.value.length - 1, index))
    clearAdvanceTimer()
    clearTransitionTimer()
    stopSpeech()
    classroomStore.stepIndex = next
    classroomStore.transitioning = true
    emitFitStep(next)
    transitionTimer = window.setTimeout(() => afterStepReady(next), FIT_MS + 60)
  }

  function startLecture(): { ok: true } | { ok: false; reason: 'empty' | 'no_diagram' } {
    const data = diagramStore.data
    if (!data?.nodes?.length) return { ok: false, reason: 'no_diagram' }

    const audienceTitle = t(
      `canvas.toolbar.professionalContent.level.${aiLevelStore.level}.title`
    )
    const mode = classroomStore.presentation
    const nextSteps = buildMindClassroomLectureSteps(
      data.nodes ?? [],
      data.connections ?? [],
      (id) => diagramStore.getMindMapDescendantIds(id),
      {
        mastery: classroomStore.mastery,
        presentation: mode,
        tourScope: classroomStore.tourScope,
        tone: classroomStore.tone,
        audienceLevel: aiLevelStore.level,
        audienceTitle,
        t: (key, params) => t(key as never, params as never),
      }
    )
    if (!nextSteps.length) return { ok: false, reason: 'empty' }

    closeActiveTool()
    classroomStore.closeModal()
    panelsStore.closeMindmate()
    panelsStore.closeNodePalette()
    setPresentationDiagramEditLocked(true)
    eventBus.emit('view:viewport_snapshot_save', {})
    classroomStore.beginSession(nextSteps, mode)
    // Dual-pane layout changes canvas size — fit after mount.
    void nextTick(() => {
      goToStep(0)
      if (mode === 'slide_deck') {
        window.setTimeout(() => goToStep(0), 160)
      }
    })
    return { ok: true }
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
    clearAdvanceTimer()
    clearTransitionTimer()
    stopSpeech()
    classroomStore.clearSession()
    diagramStore.clearSelection()
    setPresentationDiagramEditLocked(false)
    void nextTick(() => {
      eventBus.emit('view:viewport_snapshot_restore', {
        animate: true,
        duration: FIT_MS,
      })
    })
  }

  function handleKeyboard(event: KeyboardEvent): void {
    if (!isLecturing.value) return
    if (isTypingInInput()) return
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
    if (engineBootstrapped) return
    engineBootstrapped = true
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
      if (!on) stopSpeech()
    })
  }

  bootstrapEngine()

  onUnmounted(() => {
    // Keep singleton engine across mounts; only clear timers if session ends with page.
  })

  return {
    isLecturing,
    status,
    currentStep,
    stepIndex,
    steps,
    voiceEnabled,
    startLecture,
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
