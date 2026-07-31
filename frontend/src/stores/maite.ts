/**
 * Maite Learning Pinia store — workspace mode and session context.
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import type { MaiteMode, MaitePracticeItem } from '@/types/maite'

export const useMaiteStore = defineStore('maite', () => {
  const mode = ref<MaiteMode>('demo')
  const activeSessionId = ref<number | null>(null)
  const recentPractice = ref<MaitePracticeItem[]>([])
  const currentProblemText = ref('')

  const hasActiveSession = computed(() => activeSessionId.value !== null)

  function setMode(next: MaiteMode): void {
    mode.value = next
  }

  function setActiveSessionId(sessionId: number | null): void {
    activeSessionId.value = sessionId
  }

  function setRecentPractice(items: MaitePracticeItem[]): void {
    recentPractice.value = items
  }

  function setCurrentProblemText(text: string): void {
    currentProblemText.value = text
  }

  function resetWorkspace(): void {
    activeSessionId.value = null
    currentProblemText.value = ''
  }

  return {
    mode,
    activeSessionId,
    recentPractice,
    currentProblemText,
    hasActiveSession,
    setMode,
    setActiveSessionId,
    setRecentPractice,
    setCurrentProblemText,
    resetWorkspace,
  }
})
