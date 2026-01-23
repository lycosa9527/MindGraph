/**
 * DebateVerse Store - Pinia store for debate session state
 *
 * Manages debate sessions, participants, messages, and stage flow
 * with database persistence via API.
 *
 * Chinese name: 论境
 * English name: DebateVerse
 */
import { computed, ref, watch } from 'vue'

import { defineStore } from 'pinia'

import { useAuthStore } from './auth'

// ============================================================================
// Types
// ============================================================================

export type DebateStage =
  | 'setup'
  | 'coin_toss'
  | 'opening'
  | 'rebuttal'
  | 'cross_exam'
  | 'closing'
  | 'judgment'
  | 'completed'

export type ParticipantRole =
  | 'affirmative_1'
  | 'affirmative_2'
  | 'negative_1'
  | 'negative_2'
  | 'judge'
  | 'viewer'

export type UserRole = 'debater' | 'judge' | 'viewer'

export interface DebateParticipant {
  id: number
  name: string
  role: ParticipantRole
  side: string | null
  is_ai: boolean
  model_id: string | null
}

export interface DebateMessage {
  id: number
  participant_id: number
  content: string
  thinking: string | null
  stage: DebateStage
  round_number: number
  message_type: string
  audio_url: string | null
  created_at: string
}

export interface DebateSession {
  id: string
  topic: string
  current_stage: DebateStage
  status: string
  coin_toss_result: string | null
  created_at: string
  updated_at: string
}

export interface DebateSessionFull {
  session: DebateSession
  participants: DebateParticipant[]
  messages: DebateMessage[]
}

export interface LLMAssignment {
  affirmative_1: string
  affirmative_2: string
  negative_1: string
  negative_2: string
  judge: string
}

// LocalStorage types for recent debates
export interface RecentDebate {
  id: string
  topic: string
  createdAt: number
  updatedAt: number
}

interface LocalStorageData {
  recentDebates: RecentDebate[]
  savedAt: number
}

// ============================================================================
// Constants
// ============================================================================

const _AVAILABLE_MODELS = ['qwen', 'doubao', 'deepseek', 'kimi'] as const
const STORAGE_KEY = 'debateverse_recent'
const CURRENT_SESSION_KEY = 'debateverse_current_session'
const TTL_MS = 7 * 24 * 60 * 60 * 1000 // 7 days
const MAX_RECENT_DEBATES = 50

// ============================================================================
// Store
// ============================================================================

export const useDebateVerseStore = defineStore('debateverse', () => {
  // =========================================================================
  // State
  // =========================================================================

  const sessions = ref<DebateSession[]>([])
  const currentSessionId = ref<string | null>(null)
  const currentSession = ref<DebateSessionFull | null>(null)

  // User's role in current session
  const userRole = ref<UserRole | null>(null)
  const userSide = ref<string | null>(null) // 'affirmative' or 'negative'
  const userPosition = ref<number | null>(null) // 1 or 2

  // LLM assignments (from Stage 1 setup)
  const llmAssignments = ref<LLMAssignment>({
    affirmative_1: 'qwen',
    affirmative_2: 'deepseek',
    negative_1: 'doubao',
    negative_2: 'kimi',
    judge: 'deepseek',
  })

  // Streaming state
  const isStreaming = ref(false)
  const currentSpeaker = ref<number | null>(null)
  const streamingMessage = ref<Partial<DebateMessage> | null>(null)

  // TTS state
  const ttsEnabled = ref(true)
  const audioQueue = ref<string[]>([])
  const currentAudioElement = ref<HTMLAudioElement | null>(null)
  const isPlayingAudio = ref(false)

  // Abort controllers for cancelling streams
  const abortControllers = ref<Record<number, AbortController | null>>({})

  // Recent debates for localStorage
  const recentDebates = ref<RecentDebate[]>([])

  // =========================================================================
  // Computed
  // =========================================================================

  const currentStage = computed(() => currentSession.value?.session.current_stage || 'setup')

  const participants = computed(() => currentSession.value?.participants || [])

  const messages = computed(() => currentSession.value?.messages || [])

  const affirmativeParticipants = computed(() =>
    participants.value.filter((p) => p.side === 'affirmative')
  )

  const negativeParticipants = computed(() =>
    participants.value.filter((p) => p.side === 'negative')
  )

  const judgeParticipant = computed(() => participants.value.find((p) => p.role === 'judge'))

  const userParticipant = computed(() => {
    if (!userRole.value || userRole.value === 'viewer') return null
    return participants.value.find((p) => {
      if (userRole.value === 'judge') return p.role === 'judge'
      if (userRole.value === 'debater') {
        const expectedRole = `${userSide.value}_${userPosition.value}` as ParticipantRole
        return p.role === expectedRole
      }
      return false
    })
  })

  const canUserSpeak = computed(() => {
    if (!userParticipant.value) return false
    return currentSpeaker.value === userParticipant.value.id
  })

  // Sorted recent debates for display (most recent first)
  const sortedRecentDebates = computed(() => {
    return [...recentDebates.value].sort((a, b) => b.updatedAt - a.updatedAt)
  })

  // =========================================================================
  // LocalStorage Persistence
  // =========================================================================

  function saveToStorage(): void {
    try {
      const data: LocalStorageData = {
        recentDebates: recentDebates.value,
        savedAt: Date.now(),
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch (error) {
      console.warn('[DebateVerseStore] Failed to save to localStorage:', error)
    }
  }

  function loadFromStorage(): boolean {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return false

      const data: LocalStorageData = JSON.parse(raw)

      // Check TTL - remove old debates
      const now = Date.now()
      const validDebates = (data.recentDebates || []).filter(
        (debate) => now - debate.updatedAt < TTL_MS
      )

      recentDebates.value = validDebates.slice(0, MAX_RECENT_DEBATES)

      console.debug(
        `[DebateVerseStore] Loaded ${recentDebates.value.length} recent debates from localStorage`
      )
      return true
    } catch (error) {
      console.warn('[DebateVerseStore] Failed to load from localStorage:', error)
      localStorage.removeItem(STORAGE_KEY)
      return false
    }
  }

  function addRecentDebate(sessionId: string, topic: string): void {
    const now = Date.now()
    const existingIndex = recentDebates.value.findIndex((d) => d.id === sessionId)

    if (existingIndex >= 0) {
      // Update existing debate
      recentDebates.value[existingIndex].topic = topic
      recentDebates.value[existingIndex].updatedAt = now
    } else {
      // Add new debate
      recentDebates.value.push({
        id: sessionId,
        topic,
        createdAt: now,
        updatedAt: now,
      })
      // Keep only MAX_RECENT_DEBATES
      if (recentDebates.value.length > MAX_RECENT_DEBATES) {
        recentDebates.value = recentDebates.value
          .sort((a, b) => b.updatedAt - a.updatedAt)
          .slice(0, MAX_RECENT_DEBATES)
      }
    }

    saveToStorage()
  }

  function removeRecentDebate(sessionId: string): void {
    const index = recentDebates.value.findIndex((d) => d.id === sessionId)
    if (index >= 0) {
      recentDebates.value.splice(index, 1)
      saveToStorage()
    }
  }

  function renameRecentDebate(sessionId: string, newTopic: string): void {
    const debate = recentDebates.value.find((d) => d.id === sessionId)
    if (debate) {
      debate.topic = newTopic
      debate.updatedAt = Date.now()
      saveToStorage()
    }
  }

  // Auto-save on changes
  watch(
    recentDebates,
    () => {
      saveToStorage()
    },
    { deep: true }
  )

  // Load from storage on initialization
  loadFromStorage()

  // =========================================================================
  // Current Session Persistence
  // =========================================================================

  interface CurrentSessionStorage {
    sessionId: string | null
    userRole: UserRole | null
    userSide: string | null
    userPosition: number | null
    savedAt: number
  }

  function saveCurrentSessionToStorage(): void {
    try {
      const data: CurrentSessionStorage = {
        sessionId: currentSessionId.value,
        userRole: userRole.value,
        userSide: userSide.value,
        userPosition: userPosition.value,
        savedAt: Date.now(),
      }
      localStorage.setItem(CURRENT_SESSION_KEY, JSON.stringify(data))
    } catch (error) {
      console.warn('[DebateVerseStore] Failed to save current session to localStorage:', error)
    }
  }

  function loadCurrentSessionFromStorage(): void {
    try {
      const raw = localStorage.getItem(CURRENT_SESSION_KEY)
      if (!raw) return

      const data: CurrentSessionStorage = JSON.parse(raw)

      // Check TTL - restore if less than 24 hours old
      const age = Date.now() - data.savedAt
      if (age > 24 * 60 * 60 * 1000) {
        localStorage.removeItem(CURRENT_SESSION_KEY)
        return
      }

      // Restore current session ID and user role
      if (data.sessionId) {
        currentSessionId.value = data.sessionId
        userRole.value = data.userRole
        userSide.value = data.userSide
        userPosition.value = data.userPosition

        // Automatically reload the session
        loadSession(data.sessionId).catch((error) => {
          console.warn('[DebateVerseStore] Failed to reload session from storage:', error)
          // Clear invalid session
          currentSessionId.value = null
          localStorage.removeItem(CURRENT_SESSION_KEY)
        })
      }
    } catch (error) {
      console.warn('[DebateVerseStore] Failed to load current session from localStorage:', error)
      localStorage.removeItem(CURRENT_SESSION_KEY)
    }
  }

  function clearCurrentSessionStorage(): void {
    localStorage.removeItem(CURRENT_SESSION_KEY)
  }

  // Auto-save current session on changes
  watch(
    [currentSessionId, userRole, userSide, userPosition],
    () => {
      saveCurrentSessionToStorage()
    },
    { deep: true }
  )

  // Load current session on initialization
  loadCurrentSessionFromStorage()

  // =========================================================================
  // Actions
  // =========================================================================

  async function createSession(topic: string, assignments: LLMAssignment) {
    const authStore = useAuthStore()
    if (!authStore.isAuthenticated) {
      throw new Error('Authentication required')
    }

    try {
      const response = await fetch('/api/debateverse/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic,
          llm_assignments: assignments,
          format: 'us_parliamentary',
          language: 'zh',
        }),
      })

      if (!response.ok) {
        throw new Error(`Failed to create session: ${response.statusText}`)
      }

      const data = await response.json()
      currentSessionId.value = data.session_id
      llmAssignments.value = assignments

      // Add to recent debates
      addRecentDebate(data.session_id, topic)

      // Load the session
      await loadSession(data.session_id)
    } catch (error) {
      console.error('Error creating debate session:', error)
      throw error
    }
  }

  async function loadSession(sessionId: string) {
    try {
      const response = await fetch(`/api/debateverse/sessions/${sessionId}`)
      if (!response.ok) {
        throw new Error(`Failed to load session: ${response.statusText}`)
      }

      const data: DebateSessionFull = await response.json()
      currentSession.value = data
      currentSessionId.value = sessionId

      // Update recent debate timestamp
      addRecentDebate(sessionId, data.session.topic)

      // Update user role if participant
      // Note: user_id field not in API response, will be handled by backend
      // For now, check if user is in participants list
      const authStore = useAuthStore()
      if (authStore.user) {
        // TODO: Backend should include user_id in participant response
        // For now, assume user is viewer unless they created the session
        const userPart = data.participants.find((p) => !p.is_ai)
        if (userPart) {
          if (userPart.role === 'judge') {
            userRole.value = 'judge'
          } else {
            userRole.value = 'debater'
            userSide.value = userPart.side
            userPosition.value = userPart.role.includes('_1') ? 1 : 2
          }
        } else {
          userRole.value = 'viewer'
        }
      } else {
        userRole.value = 'viewer'
      }
    } catch (error) {
      console.error('Error loading debate session:', error)
      throw error
    }
  }

  async function joinSession(sessionId: string, role: UserRole, side?: string, position?: number) {
    // TODO: Implement join endpoint
    await loadSession(sessionId)
    userRole.value = role
    if (side) userSide.value = side
    if (position) userPosition.value = position
  }

  async function coinToss() {
    if (!currentSessionId.value) return

    try {
      const response = await fetch(
        `/api/debateverse/sessions/${currentSessionId.value}/coin-toss`,
        {
          method: 'POST',
        }
      )

      if (!response.ok) {
        throw new Error(`Failed to execute coin toss: ${response.statusText}`)
      }

      await loadSession(currentSessionId.value)
    } catch (error) {
      console.error('Error executing coin toss:', error)
      throw error
    }
  }

  async function advanceStage(newStage: DebateStage) {
    if (!currentSessionId.value) return

    try {
      const response = await fetch(
        `/api/debateverse/sessions/${currentSessionId.value}/advance-stage`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ new_stage: newStage }),
        }
      )

      if (!response.ok) {
        throw new Error(`Failed to advance stage: ${response.statusText}`)
      }

      await loadSession(currentSessionId.value)
    } catch (error) {
      console.error('Error advancing stage:', error)
      throw error
    }
  }

  async function sendMessage(content: string) {
    if (!currentSessionId.value || !userParticipant.value) return

    try {
      const response = await fetch(`/api/debateverse/sessions/${currentSessionId.value}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }))
        throw new Error(errorData.detail || `Failed to send message: ${response.statusText}`)
      }

      // Reload session to get updated messages
      await loadSession(currentSessionId.value)
    } catch (error) {
      console.error('Error sending message:', error)
      throw error
    }
  }

  function toggleTTS() {
    ttsEnabled.value = !ttsEnabled.value
  }

  // =========================================================================
  // Audio Playback
  // =========================================================================

  async function playAudioChunk(audioBase64: string) {
    if (!ttsEnabled.value) return

    // If there's already audio playing, queue this one
    if (isPlayingAudio.value && currentAudioElement.value) {
      audioQueue.value.push(audioBase64)
      return
    }

    try {
      // Decode base64 audio (MP3 format from Dashscope)
      const audioData = Uint8Array.from(atob(audioBase64), (c) => c.charCodeAt(0))

      // Create blob URL for MP3 audio
      const blob = new Blob([audioData], { type: 'audio/mpeg' })
      const audioUrl = URL.createObjectURL(blob)

      // Use HTMLAudioElement for MP3 playback
      const audio = new Audio(audioUrl)

      // Preload audio to reduce gaps
      audio.preload = 'auto'

      // Set volume to ensure consistent playback
      audio.volume = 1.0

      currentAudioElement.value = audio
      isPlayingAudio.value = true

      // Wait for audio to be ready before playing to reduce gaps
      await new Promise<void>((resolve, reject) => {
        const onCanPlay = () => {
          audio.removeEventListener('canplay', onCanPlay)
          audio.removeEventListener('error', onError)
          resolve()
        }
        const onError = (e: Event) => {
          audio.removeEventListener('canplay', onCanPlay)
          audio.removeEventListener('error', onError)
          reject(e)
        }
        audio.addEventListener('canplay', onCanPlay)
        audio.addEventListener('error', onError)

        // Timeout after 2 seconds
        setTimeout(() => {
          audio.removeEventListener('canplay', onCanPlay)
          audio.removeEventListener('error', onError)
          resolve() // Continue anyway
        }, 2000)
      })

      audio.onended = () => {
        URL.revokeObjectURL(audioUrl)
        currentAudioElement.value = null
        isPlayingAudio.value = false

        // Play next queued audio immediately (no delay)
        if (audioQueue.value.length > 0) {
          const nextChunk = audioQueue.value.shift()
          if (nextChunk) {
            // Use setTimeout(0) to ensure cleanup completes first
            setTimeout(() => {
              playAudioChunk(nextChunk)
            }, 0)
          }
        }
      }

      audio.onerror = (error) => {
        console.error('[DebateVerse] Audio playback error:', error)
        URL.revokeObjectURL(audioUrl)
        currentAudioElement.value = null
        isPlayingAudio.value = false

        // Try next chunk if available
        if (audioQueue.value.length > 0) {
          const nextChunk = audioQueue.value.shift()
          if (nextChunk) {
            setTimeout(() => {
              playAudioChunk(nextChunk)
            }, 0)
          }
        }
      }

      await audio.play()
    } catch (error) {
      console.error('[DebateVerse] Error playing audio chunk:', error)
      currentAudioElement.value = null
      isPlayingAudio.value = false

      // Try next chunk if available
      if (audioQueue.value.length > 0) {
        const nextChunk = audioQueue.value.shift()
        if (nextChunk) {
          setTimeout(() => {
            playAudioChunk(nextChunk)
          }, 0)
        }
      }
    }
  }

  function stopAudioPlayback() {
    if (currentAudioElement.value) {
      try {
        currentAudioElement.value.pause()
        currentAudioElement.value.currentTime = 0
        currentAudioElement.value.onended = null
        currentAudioElement.value.onerror = null
      } catch {
        // Ignore if already stopped
      }
      currentAudioElement.value = null
    }

    audioQueue.value = []
    isPlayingAudio.value = false
  }

  function setAbortController(participantId: number, controller: AbortController | null) {
    abortControllers.value[participantId] = controller
  }

  function abortAllStreams() {
    Object.values(abortControllers.value).forEach((controller) => {
      if (controller) {
        controller.abort()
      }
    })
    abortControllers.value = {}
    isStreaming.value = false
    stopAudioPlayback()
  }

  async function triggerNext() {
    if (!currentSessionId.value) return

    try {
      // Get next action (speaker or stage advance)
      const response = await fetch(
        `/api/debateverse/next?session_id=${currentSessionId.value}&language=zh`,
        {
          method: 'POST',
        }
      )

      if (!response.ok) {
        throw new Error(`Failed to get next: ${response.statusText}`)
      }

      const data = await response.json()

      // Immediately trigger the next action based on response
      if (data.action === 'trigger_speaker' && data.has_next_speaker) {
        // Immediately trigger stream for next speaker
        console.log(
          `[DebateVerse] Triggering next speaker: ${data.participant_name} (${data.participant_role})`
        )
        await streamDebaterResponse(data.participant_id, data.stage, data.language || 'zh')
      } else if (data.action === 'advance_stage' && data.next_stage) {
        // Advance to next stage
        console.log(`[DebateVerse] Advancing to next stage: ${data.next_stage}`)
        await advanceStage(data.next_stage)
      } else if (data.action === 'complete' || data.debate_complete) {
        // Debate is complete
        console.log('[DebateVerse] Debate completed')
      } else {
        console.warn('[DebateVerse] Unknown next action:', data)
      }
    } catch (error) {
      console.error('[DebateVerse] Error triggering next:', error)
      throw error
    }
  }

  async function streamDebaterResponse(
    participantId: number,
    stage: string,
    language: string = 'zh'
  ) {
    if (!currentSessionId.value) return

    // Abort any existing streams
    abortAllStreams()

    const controller = new AbortController()
    abortControllers.value[participantId] = controller
    isStreaming.value = true
    currentSpeaker.value = participantId

    try {
      console.log(
        `[DebateVerse] Starting stream for participant ${participantId} in stage ${stage}`
      )

      const response = await fetch(
        `/api/debateverse/sessions/${currentSessionId.value}/stream/${participantId}?stage=${stage}&language=${language}`,
        {
          method: 'POST',
          signal: controller.signal,
        }
      )

      if (!response.ok) {
        throw new Error(`Stream failed: ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6).trim()
            if (!jsonStr) continue

            try {
              const data = JSON.parse(jsonStr)

              if (data.type === 'token' && data.content) {
                // Update streaming message in real-time
                if (!streamingMessage.value) {
                  streamingMessage.value = {
                    participant_id: participantId,
                    content: '',
                    thinking: null,
                    stage: stage as DebateStage,
                    round_number: 0,
                    message_type: '',
                    audio_url: null,
                    created_at: new Date().toISOString(),
                  }
                }
                streamingMessage.value.content += data.content
              } else if (data.type === 'thinking' && data.content) {
                if (!streamingMessage.value) {
                  streamingMessage.value = {
                    participant_id: participantId,
                    content: '',
                    thinking: '',
                    stage: stage as DebateStage,
                    round_number: 0,
                    message_type: '',
                    audio_url: null,
                    created_at: new Date().toISOString(),
                  }
                }
                streamingMessage.value.thinking =
                  (streamingMessage.value.thinking || '') + data.content
              } else if (data.type === 'audio_chunk' && data.data) {
                // Handle audio chunk for TTS playback
                playAudioChunk(data.data)
              } else if (data.type === 'done') {
                // Stream complete, reload session to get new messages
                console.log(`[DebateVerse] Stream complete for participant ${participantId}`)
                streamingMessage.value = null
                if (currentSessionId.value) {
                  await loadSession(currentSessionId.value)
                }
                break
              } else if (data.type === 'error') {
                streamingMessage.value = null
                throw new Error(data.error || 'Stream error')
              }
            } catch (e) {
              console.warn('[DebateVerse] Failed to parse SSE:', jsonStr, e)
            }
          }
        }
      }
    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') {
        console.log(`[DebateVerse] Stream aborted for participant ${participantId}`)
      } else {
        console.error(`[DebateVerse] Stream error:`, error)
        throw error
      }
    } finally {
      abortControllers.value[participantId] = null
      currentSpeaker.value = null
      isStreaming.value = false
      streamingMessage.value = null
      // Don't stop audio here - let it finish playing naturally
    }
  }

  // =========================================================================
  // Exports
  // =========================================================================

  return {
    // State
    sessions,
    currentSessionId,
    currentSession,
    userRole,
    userSide,
    userPosition,
    llmAssignments,
    isStreaming,
    currentSpeaker,
    ttsEnabled,
    audioQueue,

    // Computed
    currentStage,
    participants,
    messages,
    affirmativeParticipants,
    negativeParticipants,
    judgeParticipant,
    userParticipant,
    canUserSpeak,
    sortedRecentDebates,
    streamingMessage,

    // Actions
    createSession,
    loadSession,
    joinSession,
    coinToss,
    advanceStage,
    sendMessage,
    toggleTTS,
    setAbortController,
    abortAllStreams,
    triggerNext,
    addRecentDebate,
    removeRecentDebate,
    renameRecentDebate,
    clearCurrentSessionStorage,
  }
})
