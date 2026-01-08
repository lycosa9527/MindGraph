/**
 * useVoiceAgent - Composable for real-time voice conversation
 *
 * Handles:
 * - WebSocket connection to voice backend
 * - Audio capture (microphone) with AudioWorklet or fallback
 * - Audio playback of AI responses
 * - Text message sending
 * - Voice transcription handling
 * - Diagram update commands from voice
 *
 * Migrated from archive/static/js/managers/voice-agent-manager.js
 */
import { computed, onUnmounted, ref, shallowRef } from 'vue'

import type { DiagramType } from '@/types'

import { eventBus } from './useEventBus'

// ============================================================================
// Types
// ============================================================================

export interface VoiceAgentOptions {
  ownerId?: string
  sampleRate?: number
  onTranscription?: (text: string) => void
  onTextChunk?: (text: string) => void
  onError?: (error: string) => void
}

export interface VoiceContext {
  diagram_type: DiagramType | string
  active_panel: string
  selected_nodes: string[]
  diagram_data: Record<string, unknown>
}

export type VoiceAgentState = 'idle' | 'connecting' | 'active' | 'listening' | 'speaking' | 'error'

interface AudioChunk {
  buffer: AudioBuffer
}

// ============================================================================
// Composable
// ============================================================================

export function useVoiceAgent(options: VoiceAgentOptions = {}) {
  const {
    ownerId = `VoiceAgent_${Date.now()}`,
    sampleRate = 24000,
    onTranscription,
    onTextChunk,
    onError,
  } = options

  // =========================================================================
  // State
  // =========================================================================

  const state = ref<VoiceAgentState>('idle')
  const sessionId = ref<string | null>(null)
  const diagramSessionId = ref<string | null>(null)
  const isActive = ref(false)
  const isVoiceActive = ref(false)
  const isPlaying = ref(false)
  const lastTranscription = ref<string | null>(null)
  const lastError = ref<string | null>(null)

  // Audio resources (shallow refs for complex objects)
  const audioContext = shallowRef<AudioContext | null>(null)
  const audioWorkletNode = shallowRef<AudioWorkletNode | null>(null)
  const audioSource = shallowRef<MediaStreamAudioSourceNode | null>(null)
  const micStream = shallowRef<MediaStream | null>(null)
  const currentAudioSource = shallowRef<AudioBufferSourceNode | null>(null)

  // WebSocket
  const ws = shallowRef<WebSocket | null>(null)

  // Audio queue for playback
  const audioQueue: AudioChunk[] = []

  // Cleanup flags
  let _destroyed = false
  let _cleaningUp = false

  // =========================================================================
  // Computed
  // =========================================================================

  const isConnected = computed(() => ws.value?.readyState === WebSocket.OPEN)
  const canSpeak = computed(() => isActive.value && isConnected.value)

  // =========================================================================
  // Audio Utilities
  // =========================================================================

  function arrayBufferToBase64(buffer: ArrayBuffer): string {
    let binary = ''
    const bytes = new Uint8Array(buffer)
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i])
    }
    return window.btoa(binary)
  }

  function base64ToArrayBuffer(base64: string): ArrayBuffer {
    const binaryString = window.atob(base64)
    const bytes = new Uint8Array(binaryString.length)
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i)
    }
    return bytes.buffer
  }

  // =========================================================================
  // Audio Playback
  // =========================================================================

  async function playAudioChunk(audioBase64: string): Promise<void> {
    if (!audioContext.value || _destroyed || _cleaningUp) return

    try {
      const audioData = base64ToArrayBuffer(audioBase64)
      const pcm16 = new Int16Array(audioData)
      const float32 = new Float32Array(pcm16.length)

      for (let i = 0; i < pcm16.length; i++) {
        float32[i] = pcm16[i] / (pcm16[i] < 0 ? 0x8000 : 0x7fff)
      }

      const audioBuffer = audioContext.value.createBuffer(1, float32.length, sampleRate)
      audioBuffer.getChannelData(0).set(float32)

      audioQueue.push({ buffer: audioBuffer })

      if (!isPlaying.value) {
        playNextAudio()
      }
    } catch (error) {
      console.error('[VoiceAgent] Audio playback error:', error)
    }
  }

  function playNextAudio(): void {
    if (_destroyed || !audioContext.value || audioContext.value.state === 'closed') {
      isPlaying.value = false
      currentAudioSource.value = null
      audioQueue.length = 0
      return
    }

    if (audioQueue.length === 0) {
      isPlaying.value = false
      currentAudioSource.value = null
      state.value = isVoiceActive.value ? 'listening' : 'active'
      return
    }

    isPlaying.value = true
    state.value = 'speaking'

    const chunk = audioQueue.shift()
    if (!chunk) return

    const source = audioContext.value.createBufferSource()
    source.buffer = chunk.buffer
    source.connect(audioContext.value.destination)

    currentAudioSource.value = source

    source.onended = () => {
      if (_destroyed) {
        currentAudioSource.value = null
        isPlaying.value = false
        return
      }
      currentAudioSource.value = null
      playNextAudio()
    }

    source.start()
  }

  function stopAudioPlayback(): void {
    if (currentAudioSource.value) {
      try {
        currentAudioSource.value.onended = null
        currentAudioSource.value.stop()
        currentAudioSource.value.disconnect()
      } catch {
        // Ignore if already stopped
      }
      currentAudioSource.value = null
    }
    audioQueue.length = 0
    isPlaying.value = false
  }

  // =========================================================================
  // Audio Capture (Microphone)
  // =========================================================================

  async function startAudioCapture(): Promise<void> {
    if (!audioContext.value || !micStream.value) {
      throw new Error('AudioContext or micStream not initialized')
    }

    // Resume AudioContext if suspended
    if (audioContext.value.state === 'suspended') {
      await audioContext.value.resume()
    }

    try {
      // Try modern AudioWorklet first
      await audioContext.value.audioWorklet.addModule('/static/js/audio/pcm-processor.js')

      const source = audioContext.value.createMediaStreamSource(micStream.value)
      const workletNode = new AudioWorkletNode(audioContext.value, 'pcm-processor')

      workletNode.port.onmessage = (event) => {
        if (!isVoiceActive.value || !ws.value || ws.value.readyState !== WebSocket.OPEN) return

        if (event.data.type === 'audio') {
          const audioBase64 = arrayBufferToBase64(event.data.data)
          ws.value.send(
            JSON.stringify({
              type: 'audio',
              data: audioBase64,
            })
          )
        }
      }

      source.connect(workletNode)
      audioWorkletNode.value = workletNode
      audioSource.value = source
    } catch {
      // Fallback to ScriptProcessor for older browsers
      console.warn('[VoiceAgent] AudioWorklet not supported, falling back to ScriptProcessor')
      await startAudioCaptureFallback()
    }
  }

  async function startAudioCaptureFallback(): Promise<void> {
    if (!audioContext.value || !micStream.value) return

    const source = audioContext.value.createMediaStreamSource(micStream.value)

    const processor = audioContext.value.createScriptProcessor(4096, 1, 1)

    processor.onaudioprocess = (e) => {
      if (!isVoiceActive.value || !ws.value || ws.value.readyState !== WebSocket.OPEN) return

      const inputData = e.inputBuffer.getChannelData(0)
      const pcm16 = new Int16Array(inputData.length)

      for (let i = 0; i < inputData.length; i++) {
        const s = Math.max(-1, Math.min(1, inputData[i]))
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
      }

      const audioBase64 = arrayBufferToBase64(pcm16.buffer)
      ws.value.send(
        JSON.stringify({
          type: 'audio',
          data: audioBase64,
        })
      )
    }

    source.connect(processor)
    processor.connect(audioContext.value.destination)
    audioSource.value = source
  }

  // =========================================================================
  // WebSocket Message Handler
  // =========================================================================

  function handleServerMessage(data: Record<string, unknown>): void {
    if (_destroyed || _cleaningUp) return

    switch (data.type) {
      case 'connected':
        sessionId.value = String(data.session_id ?? '')
        state.value = 'active'
        eventBus.emit('voice:connected', { sessionId: String(data.session_id ?? '') })
        break

      case 'transcription':
        lastTranscription.value = String(data.text ?? '')
        eventBus.emit('voice:transcription', { text: String(data.text ?? '') })
        onTranscription?.(String(data.text ?? ''))
        state.value = 'speaking'
        break

      case 'text_chunk':
        eventBus.emit('voice:text_chunk', { text: String(data.text ?? '') })
        onTextChunk?.(String(data.text ?? ''))
        break

      case 'audio_chunk':
        if (!_destroyed && !_cleaningUp) {
          playAudioChunk(String(data.audio ?? ''))
          state.value = 'speaking'
        }
        break

      case 'speech_started':
        eventBus.emit('voice:speech_started', {
          audioStartMs: typeof data.audio_start_ms === 'number' ? data.audio_start_ms : undefined,
        })
        audioQueue.length = 0 // Interrupt playback
        break

      case 'speech_stopped':
        eventBus.emit('voice:speech_stopped', {
          audioEndMs: typeof data.audio_end_ms === 'number' ? data.audio_end_ms : undefined,
        })
        break

      case 'response_done':
        eventBus.emit('voice:response_done', {})
        state.value = isVoiceActive.value ? 'listening' : 'active'
        break

      case 'action':
        executeAction(String(data.action ?? ''), (data.params as Record<string, unknown>) ?? {})
        break

      case 'diagram_update':
        applyDiagramUpdate(
          String(data.action ?? ''),
          (data.updates as Record<string, unknown>) ?? {}
        )
        break

      case 'error':
        lastError.value = String(data.error ?? '')
        state.value = 'error'
        eventBus.emit('voice:server_error', { error: String(data.error ?? '') })
        onError?.(String(data.error ?? ''))
        break

      default:
        // Forward other events through EventBus
        eventBus.emit(`voice:${data.type}` as keyof import('./useEventBus').EventTypes, data)
    }
  }

  // =========================================================================
  // Action Execution
  // =========================================================================

  function executeAction(action: string, params: Record<string, unknown>): void {
    eventBus.emit('voice:action_executed', { action, params })

    switch (action) {
      case 'open_mindmate':
      case 'open_thinkguide':
        eventBus.emit('panel:open_requested', { panel: 'mindmate', source: 'voice_agent' })
        break

      case 'close_mindmate':
      case 'close_thinkguide':
        eventBus.emit('panel:close_requested', { panel: 'mindmate', source: 'voice_agent' })
        break

      case 'open_node_palette':
        eventBus.emit('panel:open_requested', { panel: 'nodePalette', source: 'voice_agent' })
        break

      case 'close_node_palette':
        eventBus.emit('panel:close_requested', { panel: 'nodePalette', source: 'voice_agent' })
        break

      case 'close_all_panels':
        eventBus.emit('panel:close_all_requested', { source: 'voice_agent' })
        break

      case 'auto_complete':
        eventBus.emit('diagram:auto_complete_requested', { source: 'voice_agent' })
        break

      case 'select_node':
        if (params.node_id || params.node_index !== undefined) {
          eventBus.emit('selection:select_requested', {
            nodeId: params.node_id as string,
            nodeIndex: params.node_index as number,
          })
        }
        break

      case 'explain_node':
        if (params.node_id && params.node_label) {
          eventBus.emit('panel:open_requested', { panel: 'mindmate' })
          eventBus.emit('selection:highlight_requested', { nodeId: params.node_id as string })
          setTimeout(() => {
            const prompt =
              (params.prompt as string) ||
              `Explain the concept of "${params.node_label}" in simple terms.`
            eventBus.emit('mindmate:send_message', { message: prompt })
          }, 500)
        }
        break
    }
  }

  function applyDiagramUpdate(action: string, updates: Record<string, unknown>): void {
    switch (action) {
      case 'update_center':
        eventBus.emit('diagram:update_center', { ...updates, source: 'voice_agent' })
        break

      case 'update_node':
      case 'update_nodes': {
        const nodeUpdates = Array.isArray(updates) ? updates : [updates]
        eventBus.emit('diagram:update_nodes', { nodes: nodeUpdates, source: 'voice_agent' })
        break
      }

      case 'add_node':
      case 'add_nodes': {
        const nodesToAdd = Array.isArray(updates) ? updates : [updates]
        eventBus.emit('diagram:add_nodes', { nodes: nodesToAdd, source: 'voice_agent' })
        break
      }

      case 'delete_node':
      case 'remove_nodes': {
        const nodeIds = Array.isArray(updates) ? updates : [updates]
        eventBus.emit('diagram:remove_nodes', { nodeIds, source: 'voice_agent' })
        break
      }

      default:
        eventBus.emit('diagram:update_requested', { action, updates, source: 'voice_agent' })
    }
  }

  // =========================================================================
  // WebSocket Connection
  // =========================================================================

  async function connect(diagSessionId: string, context?: VoiceContext): Promise<void> {
    if (_destroyed) {
      throw new Error('Voice agent has been destroyed')
    }

    if (_cleaningUp) {
      _cleaningUp = false
    }

    // Close existing connection
    if (ws.value) {
      try {
        ws.value.onopen = null
        ws.value.onmessage = null
        ws.value.onerror = null
        ws.value.onclose = null
        ws.value.close(1001, 'Reconnecting')
      } catch {
        // Ignore
      }
      ws.value = null
    }

    diagramSessionId.value = diagSessionId
    state.value = 'connecting'

    return new Promise((resolve, reject) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      // Token is in httpOnly cookie - browser will send it automatically during WebSocket handshake
      const wsUrl = `${protocol}//${window.location.host}/ws/voice/${diagSessionId}`

      const socket = new WebSocket(wsUrl)
      ws.value = socket

      socket.onopen = () => {
        if (_cleaningUp || _destroyed) {
          socket.close()
          reject(new Error('Cleanup started during connection'))
          return
        }

        // Send start message with context
        socket.send(
          JSON.stringify({
            type: 'start',
            diagram_type: context?.diagram_type || 'circle_map',
            active_panel: context?.active_panel || 'none',
            context: context || {},
          })
        )
      }

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          handleServerMessage(data)

          if (data.type === 'connected') {
            isActive.value = true
            resolve()
          }
        } catch (error) {
          console.error('[VoiceAgent] Message parse error:', error)
        }
      }

      socket.onerror = () => {
        state.value = 'error'
        lastError.value = 'WebSocket connection failed'
        eventBus.emit('voice:ws_error', { error: lastError.value })
        reject(new Error(lastError.value))
      }

      socket.onclose = (event) => {
        isActive.value = false
        isVoiceActive.value = false
        state.value = 'idle'

        eventBus.emit('voice:ws_closed', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
        })
      }
    })
  }

  // =========================================================================
  // Public API
  // =========================================================================

  async function startConversation(diagSessionId: string, context?: VoiceContext): Promise<void> {
    if (_destroyed) {
      throw new Error('Voice agent has been destroyed')
    }

    // Initialize audio context if needed
    if (!audioContext.value) {
      audioContext.value = new (
        window.AudioContext ||
        (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext!
      )({
        sampleRate,
      })
    }

    await connect(diagSessionId, context)
    eventBus.emit('voice:started', { sessionId: sessionId.value ?? '' })
  }

  async function startVoiceInput(): Promise<void> {
    if (isVoiceActive.value) return

    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('Microphone access is not available')
    }

    // Ensure conversation is active
    if (!isActive.value) {
      throw new Error('Conversation not active')
    }

    micStream.value = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        sampleRate: 16000,
        channelCount: 1,
      },
    })

    await startAudioCapture()
    isVoiceActive.value = true
    state.value = 'listening'
  }

  function stopVoiceInput(): void {
    if (!isVoiceActive.value) return

    if (micStream.value) {
      micStream.value.getTracks().forEach((track) => track.stop())
      micStream.value = null
    }

    if (audioWorkletNode.value) {
      try {
        audioWorkletNode.value.port.postMessage({ command: 'stop' })
        audioWorkletNode.value.disconnect()
      } catch {
        // Ignore
      }
      audioWorkletNode.value = null
    }

    if (audioSource.value) {
      try {
        audioSource.value.disconnect()
      } catch {
        // Ignore
      }
      audioSource.value = null
    }

    isVoiceActive.value = false
    state.value = isActive.value ? 'active' : 'idle'
  }

  function sendTextMessage(text: string): void {
    if (!text.trim() || !ws.value || ws.value.readyState !== WebSocket.OPEN) return

    ws.value.send(
      JSON.stringify({
        type: 'text',
        text: text.trim(),
      })
    )

    state.value = 'speaking'
  }

  function updateContext(context: VoiceContext): void {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) return

    ws.value.send(
      JSON.stringify({
        type: 'context_update',
        context,
      })
    )
  }

  async function stopConversation(): Promise<void> {
    stopVoiceInput()
    stopAudioPlayback()

    if (ws.value) {
      try {
        if (ws.value.readyState === WebSocket.OPEN) {
          ws.value.send(JSON.stringify({ type: 'stop' }))
        }
        ws.value.close()
      } catch {
        // Ignore
      }
      ws.value = null
    }

    isActive.value = false
    sessionId.value = null
    state.value = 'idle'

    eventBus.emit('voice:stopped', {})
  }

  // =========================================================================
  // Cleanup
  // =========================================================================

  function cleanup(): void {
    _cleaningUp = true

    // Remove EventBus listeners
    eventBus.removeAllListenersForOwner(ownerId)

    // Stop all activity
    stopAudioPlayback()
    stopVoiceInput()

    // Suspend audio context
    if (audioContext.value && audioContext.value.state !== 'closed') {
      audioContext.value.suspend().catch(() => {})
    }

    // Close WebSocket
    if (ws.value) {
      try {
        ws.value.onopen = null
        ws.value.onmessage = null
        ws.value.onerror = null
        ws.value.onclose = null
        if (ws.value.readyState === WebSocket.OPEN) {
          ws.value.send(JSON.stringify({ type: 'stop' }))
        }
        ws.value.close()
      } catch {
        // Ignore
      }
      ws.value = null
    }

    isActive.value = false
    isVoiceActive.value = false
    state.value = 'idle'

    eventBus.emit('voice:cleanup_started', {
      diagramSessionId: diagramSessionId.value ?? undefined,
    })
  }

  function destroy(): void {
    if (_destroyed) return
    _destroyed = true

    cleanup()

    // Close audio context
    if (audioContext.value) {
      audioContext.value.close().catch(() => {})
      audioContext.value = null
    }

    eventBus.emit('voice:destroyed', {})
  }

  // =========================================================================
  // EventBus Subscriptions
  // =========================================================================

  eventBus.onWithOwner(
    'voice:start_requested',
    () => {
      if (diagramSessionId.value) {
        startConversation(diagramSessionId.value)
      }
    },
    ownerId
  )

  eventBus.onWithOwner('voice:stop_requested', () => stopConversation(), ownerId)

  eventBus.onWithOwner(
    'lifecycle:session_ending',
    (data) => {
      cleanup()
      // Call backend cleanup if needed
      if (data.sessionId && typeof window !== 'undefined') {
        // Use credentials (token in httpOnly cookie)
        fetch(`/api/voice/cleanup/${data.sessionId}`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
        }).catch(() => {})
      }
    },
    ownerId
  )

  // Auto-cleanup on unmount
  onUnmounted(() => {
    destroy()
  })

  // =========================================================================
  // Return
  // =========================================================================

  return {
    // State
    state,
    sessionId,
    diagramSessionId,
    isActive,
    isVoiceActive,
    isPlaying,
    lastTranscription,
    lastError,

    // Computed
    isConnected,
    canSpeak,

    // Actions
    startConversation,
    stopConversation,
    startVoiceInput,
    stopVoiceInput,
    sendTextMessage,
    updateContext,

    // Cleanup
    cleanup,
    destroy,
  }
}
