/**
 * Presentation mode: fullscreen, laser/spotlight, timer, zoom control handlers.
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { ANIMATION } from '@/config'
import { DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR } from '@/config/presentationHighlighter'
import { PRESENTATION_Z } from '@/config/uiConfig'
import type { PresentationHighlightStroke, PresentationToolId } from '@/types'

const TIMER_DEFAULT_SECONDS = 300
const SPOTLIGHT_INNER_RADIUS_PX = 150
const SPOTLIGHT_OUTER_RADIUS_PX = 195
const LASER_CURSOR_BASE_PX = 22
const PRESENTATION_POINTER_SCALE_MIN = 0.5
const PRESENTATION_POINTER_SCALE_MAX = 2.5
const PRESENTATION_POINTER_SCALE_STEP = 0.1

export function useCanvasPagePresentation() {
  const notify = useNotifications()
  const { t } = useLanguage()

  const canvasZoom = ref<number | null>(null)
  const handToolActive = ref(false)
  const isPresentationMode = ref(false)
  const presentationTool = ref<PresentationToolId>('laser')
  const presentationHighlighterColor = ref(DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR)
  const presentationHighlightStrokes = ref<PresentationHighlightStroke[]>([])
  const canvasPageRef = ref<HTMLElement | null>(null)

  const presentationHighlighterActive = computed(
    () => presentationTool.value === 'highlighter' || presentationTool.value === 'pen'
  )

  const presentationPointerSizeScale = ref(1)

  const timerTotalSeconds = ref(TIMER_DEFAULT_SECONDS)
  const timerRemainingSeconds = ref(TIMER_DEFAULT_SECONDS)
  const timerRunning = ref(false)
  let timerTickId: ReturnType<typeof setInterval> | null = null

  function clearPresentationTimerTick(): void {
    if (timerTickId !== null) {
      clearInterval(timerTickId)
      timerTickId = null
    }
  }

  function startPresentationTimerTick(): void {
    clearPresentationTimerTick()
    timerTickId = window.setInterval(() => {
      if (!timerRunning.value) {
        return
      }
      if (timerRemainingSeconds.value <= 0) {
        timerRunning.value = false
        clearPresentationTimerTick()
        return
      }
      timerRemainingSeconds.value -= 1
    }, 1000)
  }

  watch(timerRunning, (run) => {
    if (run) {
      startPresentationTimerTick()
    } else {
      clearPresentationTimerTick()
    }
  })

  watch(presentationTool, (tool) => {
    if (tool !== 'timer') {
      timerRunning.value = false
    }
  })

  function onTimerToggleRun(): void {
    if (timerRemainingSeconds.value <= 0 && !timerRunning.value) {
      timerRemainingSeconds.value = timerTotalSeconds.value
    }
    timerRunning.value = !timerRunning.value
  }

  function onTimerReset(): void {
    timerRunning.value = false
    timerRemainingSeconds.value = timerTotalSeconds.value
  }

  function onTimerPresetMinutes(minutes: number): void {
    const s = Math.max(60, minutes * 60)
    timerTotalSeconds.value = s
    timerRemainingSeconds.value = s
    timerRunning.value = true
  }

  function onTimerExit(): void {
    timerRunning.value = false
    presentationTool.value = 'laser'
  }

  function onTimerSetMinutes(minutes: number): void {
    const m = Math.min(180, Math.max(1, Math.round(minutes)))
    onTimerPresetMinutes(m)
  }

  const laserX = ref(0)
  const laserY = ref(0)

  function handleLaserMouseMove(event: MouseEvent) {
    laserX.value = event.clientX
    laserY.value = event.clientY
  }

  const spotlightStyle = computed(() => {
    const s = presentationPointerSizeScale.value
    const inner = SPOTLIGHT_INNER_RADIUS_PX * s
    const outer = SPOTLIGHT_OUTER_RADIUS_PX * s
    return {
      zIndex: PRESENTATION_Z.SPOTLIGHT,
      background: `radial-gradient(circle at ${laserX.value}px ${laserY.value}px, transparent 0%, transparent ${inner}px, rgba(0,0,0,0.62) ${outer}px)`,
    }
  })

  const laserCursorStyle = computed(() => {
    const s = presentationPointerSizeScale.value
    const size = LASER_CURSOR_BASE_PX * s
    const half = size / 2
    return {
      zIndex: PRESENTATION_Z.LASER,
      transform: `translate(${laserX.value}px, ${laserY.value}px)`,
      width: `${size}px`,
      height: `${size}px`,
      marginLeft: `-${half}px`,
      marginTop: `-${half}px`,
      boxShadow: [
        `0 0 ${4 * s}px ${2 * s}px rgba(255, 255, 255, 0.9)`,
        `0 0 ${10 * s}px ${4 * s}px rgba(255, 60, 60, 1)`,
        `0 0 ${22 * s}px ${8 * s}px rgba(220, 20, 20, 0.85)`,
        `0 0 ${45 * s}px ${18 * s}px rgba(180, 0, 0, 0.55)`,
        `0 0 ${80 * s}px ${35 * s}px rgba(140, 0, 0, 0.25)`,
      ].join(', '),
    }
  })

  function isTypingInInput(): boolean {
    const active = document.activeElement as HTMLElement
    return (
      active?.tagName === 'INPUT' || active?.tagName === 'TEXTAREA' || !!active?.isContentEditable
    )
  }

  function handlePresentationPointerSizeKeydown(event: KeyboardEvent) {
    if (!isPresentationMode.value) return
    if (!event.ctrlKey && !event.metaKey) return
    if (isTypingInInput()) return

    const code = event.code
    const key = event.key
    const increase = key === '+' || key === '=' || code === 'Equal' || code === 'NumpadAdd'
    const decrease = key === '-' || key === '_' || code === 'Minus' || code === 'NumpadSubtract'
    if (!increase && !decrease) return

    event.preventDefault()
    const delta = increase ? PRESENTATION_POINTER_SCALE_STEP : -PRESENTATION_POINTER_SCALE_STEP
    presentationPointerSizeScale.value = Math.min(
      PRESENTATION_POINTER_SCALE_MAX,
      Math.max(PRESENTATION_POINTER_SCALE_MIN, presentationPointerSizeScale.value + delta)
    )
  }

  watch(isPresentationMode, (active) => {
    if (active) {
      window.addEventListener('mousemove', handleLaserMouseMove)
      window.addEventListener('keydown', handlePresentationPointerSizeKeydown, true)
      presentationTool.value = 'laser'
      timerRunning.value = false
      clearPresentationTimerTick()
      timerTotalSeconds.value = TIMER_DEFAULT_SECONDS
      timerRemainingSeconds.value = TIMER_DEFAULT_SECONDS
    } else {
      window.removeEventListener('mousemove', handleLaserMouseMove)
      window.removeEventListener('keydown', handlePresentationPointerSizeKeydown, true)
      presentationHighlightStrokes.value = []
      presentationTool.value = 'laser'
      presentationHighlighterColor.value = DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR
      presentationPointerSizeScale.value = 1
      timerRunning.value = false
      clearPresentationTimerTick()
      timerTotalSeconds.value = TIMER_DEFAULT_SECONDS
      timerRemainingSeconds.value = TIMER_DEFAULT_SECONDS
    }
  })

  function emitFitToCanvas() {
    eventBus.emit('view:fit_to_canvas_requested', { animate: true })
  }

  function handleFullscreenChange() {
    if (document.fullscreenElement) {
      isPresentationMode.value = true
      setTimeout(emitFitToCanvas, ANIMATION.FIT_VIEWPORT_DELAY)
    } else {
      isPresentationMode.value = false
      nextTick().then(() => {
        setTimeout(emitFitToCanvas, ANIMATION.FIT_VIEWPORT_DELAY)
      })
    }
  }

  function handleZoomChange(level: number) {
    const zoom = Math.max(0.1, Math.min(4, level / 100))
    eventBus.emit('view:zoom_set_requested', { zoom })
  }

  function handleZoomIn() {
    eventBus.emit('view:zoom_in_requested', {})
  }

  function handleZoomOut() {
    eventBus.emit('view:zoom_out_requested', {})
  }

  function handleFitToScreen() {
    eventBus.emit('view:fit_to_canvas_requested', { animate: true })
  }

  function handleHandToolToggle(active: boolean) {
    handToolActive.value = active
  }

  async function handleStartPresentation() {
    if (isPresentationMode.value) {
      if (document.fullscreenElement) {
        await document.exitFullscreen()
      }
      return
    }

    if (!canvasPageRef.value) return

    try {
      await canvasPageRef.value.requestFullscreen()
    } catch (err) {
      console.warn('Fullscreen request failed:', err)
      notify.error(t('notification.fullscreenFailed'))
    }
  }

  function handleModelChange(model: string) {
    console.log('Selected model:', model)
  }

  onMounted(() => {
    document.addEventListener('fullscreenchange', handleFullscreenChange)
  })

  onUnmounted(() => {
    document.removeEventListener('fullscreenchange', handleFullscreenChange)
    window.removeEventListener('mousemove', handleLaserMouseMove)
    window.removeEventListener('keydown', handlePresentationPointerSizeKeydown, true)
    clearPresentationTimerTick()
  })

  function resetPresentationStateOnLeave(): void {
    handToolActive.value = false
    isPresentationMode.value = false
    presentationHighlightStrokes.value = []
    presentationTool.value = 'laser'
    presentationHighlighterColor.value = DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR
    presentationPointerSizeScale.value = 1
  }

  return {
    canvasPageRef,
    canvasZoom,
    handToolActive,
    isPresentationMode,
    presentationTool,
    presentationHighlighterColor,
    presentationHighlightStrokes,
    presentationHighlighterActive,
    presentationPointerSizeScale,
    timerTotalSeconds,
    timerRemainingSeconds,
    timerRunning,
    onTimerToggleRun,
    onTimerReset,
    onTimerPresetMinutes,
    onTimerExit,
    onTimerSetMinutes,
    laserCursorStyle,
    spotlightStyle,
    handleZoomChange,
    handleZoomIn,
    handleZoomOut,
    handleFitToScreen,
    handleHandToolToggle,
    handleStartPresentation,
    handleModelChange,
    clearPresentationTimerTick,
    resetPresentationStateOnLeave,
  }
}
