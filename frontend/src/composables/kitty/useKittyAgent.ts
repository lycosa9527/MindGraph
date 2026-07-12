/**
 * useKittyAgent — Kitty Agent WebSocket client (text-first; Fun-ASR / CosyVoice).
 */
import { computed, onUnmounted, ref, shallowRef } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { arrayBufferToBase64 } from '@/composables/kitty/kittyAgentAudioCodec'
import {
  createKittyCapture,
  createKittyPlayback,
  handleKittyServerMessage,
} from '@/composables/kitty/kittyAgentInbound'
import type {
  KittyAgentContext,
  KittyAgentOptions,
  KittyAgentState,
  KittyAudioChunk,
  KittyContextUpdateOptions,
} from '@/composables/kitty/kittyAgentTypes'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import { useKittySessionStore } from '@/stores/kittySession'

export type {
  KittyAgentContext,
  KittyAgentOptions,
  KittyAgentState,
  KittyContextUpdateOptions,
  KittyLibrarySnapshot,
} from '@/composables/kitty/kittyAgentTypes'

const KITTY_CONNECT_TIMEOUT_MS = 10000

export function useKittyAgent(options: KittyAgentOptions = {}) {
  const {
    ownerId = `KittyAgent_${Date.now()}`,
    sampleRate = 24000,
    kittyClientLane,
    textOnly = true,
    onTranscription,
    onTextChunk,
    onError,
    buildContext: initialBuildContext,
  } = options

  const diagramContextBuilder = { fn: initialBuildContext as (() => KittyAgentContext) | undefined }

  const state = ref<KittyAgentState>('idle')
  const sessionId = ref<string | null>(null)
  const diagramSessionId = ref<string | null>(null)
  const isActive = ref(false)
  const isVoiceActive = ref(false)
  const isPlaying = ref(false)
  const lastTranscription = ref<string | null>(null)
  const lastError = ref<string | null>(null)
  const kittySession = useKittySessionStore()
  const hubScopeRevision = computed({
    get: () => kittySession.hubScopeRevision,
    set: (value: number | null) => {
      kittySession.setHubScopeRevision(value)
    },
  })

  const audioContext = shallowRef<AudioContext | null>(null)
  const audioWorkletNode = shallowRef<AudioWorkletNode | null>(null)
  const audioScriptProcessor = shallowRef<ScriptProcessorNode | null>(null)
  const audioSource = shallowRef<MediaStreamAudioSourceNode | null>(null)
  const micStream = shallowRef<MediaStream | null>(null)
  const currentAudioSource = shallowRef<AudioBufferSourceNode | null>(null)
  const ws = shallowRef<WebSocket | null>(null)

  const audioQueue: KittyAudioChunk[] = []

  let destroyed = false
  let cleaningUp = false
  /** Serializes startConversation so two callers cannot open two sockets for one agent. */
  let startInFlight: Promise<void> | null = null
  /** Bumped on every start/stop so queued starts can detect supersession. */
  let startGeneration = 0
  /**
   * Active handshake owner. stop/cleanup/supersede must settle this immediately —
   * never leave the promise hanging until the 10s wall-clock timeout.
   */
  let activeConnectAttempt: {
    socket: WebSocket
    scope: string
    settleReject: (err: Error) => void
  } | null = null

  const isConnected = computed(() => ws.value?.readyState === WebSocket.OPEN)
  const canSpeak = computed(() => isActive.value && isConnected.value)

  function isLiveOnScope(scope: string): boolean {
    if (diagramSessionId.value !== scope) {
      return false
    }
    const socket = ws.value
    if (!socket) {
      return false
    }
    return socket.readyState === WebSocket.OPEN && isActive.value
  }

  /** Drop isActive/state when the socket is gone or no longer OPEN. */
  function reconcileLiveState(): void {
    const socket = ws.value
    if (socket?.readyState === WebSocket.OPEN && isActive.value) {
      return
    }
    if (!isActive.value) {
      return
    }
    isActive.value = false
    if (
      state.value === 'connecting' ||
      state.value === 'active' ||
      state.value === 'listening'
    ) {
      state.value = 'idle'
    }
  }

  async function joinSupersedingStart(
    scope: string,
    myGeneration: number,
    context?: KittyAgentContext
  ): Promise<void> {
    const targetGeneration = startGeneration
    const deadline = Date.now() + KITTY_CONNECT_TIMEOUT_MS
    let winnerStarted = false
    while (Date.now() < deadline) {
      if (startInFlight !== null) {
        winnerStarted = true
      }
      if (
        winnerStarted &&
        startInFlight === null &&
        startGeneration === targetGeneration
      ) {
        if (isLiveOnScope(scope)) {
          if (context) {
            updateContext(context)
          }
          return
        }
        break
      }
      await new Promise<void>((resolve) => {
        setTimeout(resolve, 25)
      })
    }
    if (isLiveOnScope(scope)) {
      if (context) {
        updateContext(context)
      }
      return
    }
    throw new Error(
      `Kitty connection superseded (gen ${myGeneration} → ${startGeneration}) ` +
        `before ${scope.slice(0, 8)} became live`
    )
  }

  const lifecycle = {
    destroyed: () => destroyed,
    cleaningUp: () => cleaningUp,
  }

  function detachSocketHandlers(socket: WebSocket): void {
    socket.onopen = null
    socket.onmessage = null
    socket.onerror = null
    socket.onclose = null
  }

  function cancelActiveConnectAttempt(reason: string): void {
    const attempt = activeConnectAttempt
    if (!attempt) {
      return
    }
    activeConnectAttempt = null
    if (ws.value === attempt.socket) {
      ws.value = null
      isActive.value = false
      if (state.value === 'connecting' || state.value === 'active') {
        state.value = 'idle'
      }
    }
    detachSocketHandlers(attempt.socket)
    try {
      attempt.socket.close(1000, reason)
    } catch {
      /* ignore */
    }
    attempt.settleReject(new Error(reason))
  }

  const { playAudioChunk, stopAudioPlayback } = createKittyPlayback({
    ...lifecycle,
    sampleRate,
    audioContext,
    isVoiceActive,
    isPlaying,
    state,
    currentAudioSource,
    audioQueue,
  })

  const { startAudioCapture } = createKittyCapture({
    isVoiceActive,
    ws,
    audioContext,
    micStream,
    audioWorkletNode,
    audioScriptProcessor,
    audioSource,
  })

  function handleServerMessage(data: Record<string, unknown>): void {
    if (data.type === 'context_mutation_ack' && typeof data.revision === 'number') {
      kittySession.setHubScopeRevision(data.revision)
    }
    handleKittyServerMessage(data, {
      ...lifecycle,
      textOnly,
      isVoiceActive,
      state,
      sessionId,
      lastTranscription,
      lastError,
      onTranscription,
      onTextChunk,
      onError,
      playAudioChunk,
      stopAudioPlayback,
      hubScopeRevision: kittySession.hubScopeRevision,
      diagramSessionId: diagramSessionId.value,
      buildDiagramContext: diagramContextBuilder.fn,
      updateContext,
      sendDiagramMutationAck: (payload) => {
        if (ws.value?.readyState === WebSocket.OPEN) {
          ws.value.send(JSON.stringify(payload))
        }
      },
    })
  }

  async function connect(diagSessionId: string, context?: KittyAgentContext): Promise<void> {
    if (destroyed) {
      throw new Error('Kitty Agent has been destroyed')
    }

    if (cleaningUp) {
      cleaningUp = false
    }

    cancelActiveConnectAttempt('Connection superseded by a newer socket')

    const previousSocket = ws.value
    if (previousSocket) {
      stopVoiceInput()
      stopAudioPlayback()
      if (ws.value === previousSocket) {
        ws.value = null
      }
      try {
        detachSocketHandlers(previousSocket)
        previousSocket.close(1001, 'Reconnecting')
      } catch {
        /* ignore */
      }
    }

    diagramSessionId.value = diagSessionId
    // New Kitty WS → Hub scope revision may restart; never carry a stale expected_revision.
    kittySession.setHubScopeRevision(null)
    state.value = 'connecting'
    isActive.value = false
    traceKittyWorkflow('mobile', 'ws_connect', `scope=${diagSessionId.slice(0, 12)}`, {
      scope: diagSessionId,
    })

    return new Promise((resolve, reject) => {
      let settled = false
      let handshakeTimeout: ReturnType<typeof setTimeout> | null = null
      const clearHandshakeTimeout = (): void => {
        if (handshakeTimeout != null) {
          clearTimeout(handshakeTimeout)
          handshakeTimeout = null
        }
      }
      const settleResolve = (): void => {
        if (settled) return
        settled = true
        if (activeConnectAttempt?.socket === socket) {
          activeConnectAttempt = null
        }
        clearHandshakeTimeout()
        resolve()
      }
      const settleReject = (err: Error): void => {
        if (settled) return
        settled = true
        if (activeConnectAttempt?.socket === socket) {
          activeConnectAttempt = null
        }
        clearHandshakeTimeout()
        reject(err)
      }

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws/kitty/${diagSessionId}`
      const socket = new WebSocket(wsUrl)
      ws.value = socket
      activeConnectAttempt = { socket, scope: diagSessionId, settleReject }
      handshakeTimeout = setTimeout(() => {
        if (ws.value === socket) {
          ws.value = null
          isActive.value = false
          state.value = 'error'
          lastError.value = 'WebSocket connection timed out'
          detachSocketHandlers(socket)
          try {
            socket.close(1000, 'Connection timeout')
          } catch {
            /* ignore */
          }
          eventBus.emit('voice:ws_error', { error: lastError.value })
        }
        settleReject(new Error('WebSocket connection timed out'))
      }, KITTY_CONNECT_TIMEOUT_MS)

      socket.onopen = () => {
        if (ws.value !== socket) {
          settleReject(new Error('Connection superseded by a newer socket'))
          return
        }
        if (cleaningUp || destroyed) {
          socket.close()
          settleReject(new Error('Cleanup started during connection'))
          return
        }

        const startPayload: Record<string, unknown> = {
          type: 'start',
          diagram_type: context?.diagram_type || 'circle_map',
          active_panel: context?.active_panel || 'none',
          context: context || {},
        }
        if (textOnly) {
          startPayload.client_mode = 'text'
        }
        if (kittyClientLane === 'mobile') {
          startPayload.client_lane = 'mobile'
        }
        socket.send(JSON.stringify(startPayload))
      }

      socket.onmessage = (event) => {
        if (ws.value !== socket) {
          return
        }
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'connected') {
            isActive.value = true
            settleResolve()
          }
          handleServerMessage(data)
        } catch (error) {
          console.error('[KittyAgent] Message parse error:', error)
        }
      }

      socket.onerror = () => {
        if (ws.value !== socket) {
          settleReject(new Error('Connection superseded by a newer socket'))
          return
        }
        state.value = 'error'
        lastError.value = 'WebSocket connection failed'
        eventBus.emit('voice:ws_error', { error: lastError.value })
        settleReject(new Error(lastError.value))
      }

      socket.onclose = (event) => {
        if (ws.value !== socket) {
          if (!settled) {
            settleReject(new Error('Connection superseded by a newer socket'))
          }
          return
        }
        ws.value = null
        stopVoiceInput()
        stopAudioPlayback()
        isActive.value = false
        isVoiceActive.value = false
        state.value = 'idle'
        eventBus.emit('voice:ws_closed', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
        })
        if (!settled) {
          settleReject(new Error(event.reason || 'WebSocket closed before connected'))
        }
      }
    })
  }

  async function startConversation(
    diagSessionId: string,
    context?: KittyAgentContext
  ): Promise<void> {
    if (destroyed) {
      throw new Error('Kitty Agent has been destroyed')
    }

    const scope = diagSessionId.trim()
    if (!scope) {
      throw new Error('Missing Kitty diagram session id')
    }

    const myGeneration = ++startGeneration

    // Join any in-flight start so we never open a second socket for this agent.
    const prior = startInFlight
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    startInFlight = gate
    let gateReleased = false
    const finishGate = (): void => {
      if (gateReleased) {
        return
      }
      gateReleased = true
      release()
      if (startInFlight === gate) {
        startInFlight = null
      }
    }

    try {
      if (prior) {
        await prior.catch(() => undefined)
      }

      // A newer startConversation superseded this waiter — join the winner so
      // callers (PTT ensureConnected) never return while the socket is still dead.
      if (myGeneration !== startGeneration) {
        finishGate()
        await joinSupersedingStart(scope, myGeneration, context)
        return
      }

      if (isLiveOnScope(scope)) {
        if (context) {
          updateContext(context)
        }
        return
      }

      if (!audioContext.value) {
        const AudioCtx =
          window.AudioContext ||
          (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
        if (!AudioCtx) {
          throw new Error('Web Audio API is not supported')
        }
        audioContext.value = new AudioCtx({ sampleRate })
      }

      // Opening a text-first Kitty session must not depend on Web Audio. Safari
      // can leave resume() pending outside a user gesture, which previously
      // prevented connect() from creating the WebSocket at all. Playback and
      // legacy capture resume the context when they actually need audio.
      await connect(scope, context)

      if (myGeneration !== startGeneration) {
        finishGate()
        await joinSupersedingStart(scope, myGeneration, context)
        return
      }

      kittySession.setOwnsKittySession(true)
      eventBus.emit('voice:started', { sessionId: sessionId.value ?? '' })
    } finally {
      finishGate()
    }
  }

  async function startVoiceInput(): Promise<void> {
    if (isVoiceActive.value) return

    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('Microphone access is not available')
    }
    if (!isActive.value) {
      throw new Error('Conversation not active')
    }

    stopAudioPlayback()
    if (!isVoiceActive.value && isActive.value) {
      state.value = 'active'
    }
    try {
      if (ws.value && ws.value.readyState === WebSocket.OPEN) {
        ws.value.send(JSON.stringify({ type: 'cancel_response' }))
      }
    } catch {
      /* ignore */
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
        audioWorkletNode.value.port.onmessage = null
        audioWorkletNode.value.port.postMessage({ command: 'stop' })
        audioWorkletNode.value.disconnect()
      } catch {
        /* ignore */
      }
      audioWorkletNode.value = null
    }

    if (audioScriptProcessor.value) {
      try {
        audioScriptProcessor.value.onaudioprocess = null
        audioScriptProcessor.value.disconnect()
      } catch {
        /* ignore */
      }
      audioScriptProcessor.value = null
    }

    if (audioSource.value) {
      try {
        audioSource.value.disconnect()
      } catch {
        /* ignore */
      }
      audioSource.value = null
    }

    isVoiceActive.value = false
    state.value = isActive.value ? 'active' : 'idle'
  }

  function sendTextMessage(text: string, requestId?: string): boolean {
    if (!text.trim() || !ws.value || ws.value.readyState !== WebSocket.OPEN) {
      return false
    }
    stopAudioPlayback()
    try {
      ws.value.send(JSON.stringify({ type: 'tts_interrupt' }))
    } catch {
      /* ignore */
    }
    traceKittyWorkflow('mobile', 'text_send', text.trim().slice(0, 120))
    const payload: Record<string, string> = { type: 'text', text: text.trim() }
    if (requestId && requestId.trim()) {
      payload.request_id = requestId.trim()
    }
    try {
      ws.value.send(JSON.stringify(payload))
    } catch {
      return false
    }
    state.value = textOnly ? 'active' : 'speaking'
    return true
  }

  function setTtsEnabled(enabled: boolean): void {
    kittySession.setTtsEnabled(enabled)
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) return
    ws.value.send(JSON.stringify({ type: 'tts_set_enabled', enabled }))
    if (!enabled) {
      stopAudioPlayback()
      ws.value.send(JSON.stringify({ type: 'tts_interrupt' }))
    }
  }

  function updateContext(context: KittyAgentContext, options?: KittyContextUpdateOptions): void {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) return
    const payload: Record<string, unknown> = { type: 'context_update', context }
    if (options?.persistLibrary === true) {
      payload.persist_library = true
    }
    if (options?.librarySnapshot != null) {
      payload.library_snapshot = options.librarySnapshot
    }
    if (options?.idempotencyKey != null && options.idempotencyKey.trim() !== '') {
      payload.idempotency_key = options.idempotencyKey.trim()
    }
    const rev = options?.expectedRevision ?? hubScopeRevision.value
    if (typeof rev === 'number') {
      payload.expected_revision = rev
    }
    const persist = options?.persistLibrary === true
    traceKittyWorkflow(
      'hub',
      'context_send',
      `${persist ? 'persist ' : ''}rev=${typeof rev === 'number' ? rev : '?'}`,
      { scope: diagramSessionId.value ?? undefined }
    )
    ws.value.send(JSON.stringify(payload))
  }

  function sendMinimalAudioPreamble(): void {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) return
    const rate = 24000
    const ms = 100
    const samples = Math.max(1, Math.floor((rate * ms) / 1000))
    const pcm = new Int16Array(samples)
    ws.value.send(
      JSON.stringify({
        type: 'audio',
        data: arrayBufferToBase64(pcm.buffer),
      })
    )
  }

  function sendAppendImage(dataBase64: string, format = 'jpeg'): void {
    if (!dataBase64 || !ws.value || ws.value.readyState !== WebSocket.OPEN) return
    traceKittyWorkflow('mobile', 'image_send', `format=${format}`)
    sendMinimalAudioPreamble()
    ws.value.send(
      JSON.stringify({
        type: 'append_image',
        data: dataBase64,
        format,
      })
    )
  }

  async function stopConversation(): Promise<void> {
    startGeneration += 1
    cancelActiveConnectAttempt('Conversation stopped')
    stopVoiceInput()
    stopAudioPlayback()

    const socket = ws.value
    if (socket) {
      if (ws.value === socket) {
        ws.value = null
      }
      try {
        detachSocketHandlers(socket)
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: 'stop' }))
        }
        socket.close()
      } catch {
        /* ignore */
      }
    }

    isActive.value = false
    sessionId.value = null
    state.value = 'idle'
    eventBus.emit('voice:stopped', {})
  }

  function cleanup(): void {
    cleaningUp = true
    startGeneration += 1
    cancelActiveConnectAttempt('Cleanup started during connection')
    eventBus.removeAllListenersForOwner(ownerId)
    stopAudioPlayback()
    stopVoiceInput()

    if (audioContext.value && audioContext.value.state !== 'closed') {
      audioContext.value.suspend().catch(() => {})
    }

    if (ws.value) {
      try {
        detachSocketHandlers(ws.value)
        if (ws.value.readyState === WebSocket.OPEN) {
          ws.value.send(JSON.stringify({ type: 'stop' }))
        }
        ws.value.close()
      } catch {
        /* ignore */
      }
      ws.value = null
    }

    isActive.value = false
    isVoiceActive.value = false
    state.value = 'idle'
    kittySession.setOwnsKittySession(false)
    eventBus.emit('voice:cleanup_started', {
      diagramSessionId: diagramSessionId.value ?? undefined,
    })
  }

  function destroy(): void {
    if (destroyed) return
    destroyed = true
    cleanup()
    if (audioContext.value) {
      audioContext.value.close().catch(() => {})
      audioContext.value = null
    }
    eventBus.emit('voice:destroyed', {})
  }

  eventBus.onWithOwner('voice:stop_requested', () => void stopConversation(), ownerId)

  eventBus.onWithOwner(
    'lifecycle:session_ending',
    (data) => {
      cleanup()
      if (data.sessionId && typeof window !== 'undefined') {
        fetch(`/api/kitty/cleanup/${data.sessionId}`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
        }).catch(() => {})
      }
    },
    ownerId
  )

  onUnmounted(() => {
    destroy()
  })

  function registerDiagramContextBuilder(fn: () => KittyAgentContext): void {
    diagramContextBuilder.fn = fn
  }

  return {
    state,
    sessionId,
    diagramSessionId,
    isActive,
    isVoiceActive,
    isPlaying,
    lastTranscription,
    lastError,
    isConnected,
    canSpeak,
    isLiveForScope: isLiveOnScope,
    reconcileLiveState,
    ws,
    startConversation,
    stopConversation,
    startVoiceInput,
    stopVoiceInput,
    sendTextMessage,
    setTtsEnabled,
    stopAudioPlayback,
    updateContext,
    registerDiagramContextBuilder,
    sendAppendImage,
    sendMinimalAudioPreamble,
    cleanup,
    destroy,
  }
}
