/**
 * Lecture caption playback — Kitty TTS with browser speech fallback.
 */
import { eventBus } from '@/composables/core/useEventBus'
import { useMindClassroomStore } from '@/stores/mindClassroom'
import { lectureTtsSafetyMs } from '@/utils/mindClassroomScript'

export function lectureSpeakGeneration(): number {
  return useMindClassroomStore().speakGeneration
}

export function stopLectureSpeech(): void {
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
  window.speechSynthesis.cancel()
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

export function speakLectureCaption(
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

export function isLectureTypingInInput(): boolean {
  const active = document.activeElement as HTMLElement | null
  return (
    active?.tagName === 'INPUT' ||
    active?.tagName === 'TEXTAREA' ||
    Boolean(active?.isContentEditable)
  )
}

export function isLectureInteractiveTarget(target: EventTarget | null): boolean {
  return (
    target instanceof Element &&
    Boolean(
      target.closest(
        'button, a, input, select, textarea, [contenteditable="true"], [role="option"], [role="radio"]'
      )
    )
  )
}
