/**
 * Voice Store - Pinia store for voice agent state
 * Migrated from StateManager.voice
 *
 * Enhanced with State-to-Event bridge for global EventBus integration
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { eventBus } from '@/composables/useEventBus'

export const useVoiceStore = defineStore('voice', () => {
  // State
  const active = ref(false)
  const sessionId = ref<string | null>(null)
  const lastTranscription = ref('')
  const isListening = ref(false)
  const isSpeaking = ref(false)

  // Getters
  const isActive = computed(() => active.value)
  const hasSession = computed(() => !!sessionId.value)

  // Actions
  function startSession(id: string): void {
    sessionId.value = id
    active.value = true
    eventBus.emit('voice:started', { sessionId: id })
    eventBus.emit('state:voice_updated', { updates: { active: true, sessionId: id } })
  }

  function endSession(): void {
    const oldSessionId = sessionId.value
    sessionId.value = null
    active.value = false
    isListening.value = false
    isSpeaking.value = false
    lastTranscription.value = ''
    eventBus.emit('voice:stopped', {})
    eventBus.emit('state:voice_updated', {
      updates: { active: false, sessionId: null, oldSessionId },
    })
  }

  function setListening(listening: boolean): void {
    isListening.value = listening
  }

  function setSpeaking(speaking: boolean): void {
    isSpeaking.value = speaking
  }

  function setTranscription(text: string): void {
    lastTranscription.value = text
  }

  function startListening(): void {
    isListening.value = true
    isSpeaking.value = false
  }

  function stopListening(): void {
    isListening.value = false
  }

  function update(updates: {
    active?: boolean
    sessionId?: string | null
    lastTranscription?: string
    isListening?: boolean
    isSpeaking?: boolean
  }): void {
    if (updates.active !== undefined) active.value = updates.active
    if (updates.sessionId !== undefined) sessionId.value = updates.sessionId
    if (updates.lastTranscription !== undefined) lastTranscription.value = updates.lastTranscription
    if (updates.isListening !== undefined) isListening.value = updates.isListening
    if (updates.isSpeaking !== undefined) isSpeaking.value = updates.isSpeaking
  }

  function reset(): void {
    active.value = false
    sessionId.value = null
    lastTranscription.value = ''
    isListening.value = false
    isSpeaking.value = false
  }

  return {
    // State
    active,
    sessionId,
    lastTranscription,
    isListening,
    isSpeaking,

    // Getters
    isActive,
    hasSession,

    // Actions
    startSession,
    endSession,
    setListening,
    setSpeaking,
    setTranscription,
    startListening,
    stopListening,
    update,
    reset,
  }
})
