/**
 * Fun-ASR mic capture for Kitty (PCM 16 kHz mono → Kitty WS).
 *
 * Mobile PTT (iOS Safari — BotFramework-WebChat + ptt-radio patterns):
 * - One warmed AudioContext + MediaStream across holds
 * - pointerdown: blessAudioContextSync + prepareMicFromUserGesture (gesture stack)
 * - Hold: track.enabled=true + asr_start; release: asr_stop + track.enabled=false
 * - teardownWarmMic() only on page leave
 * - Every ASR message carries utterance_id for hold correlation
 */
import { type Ref, type ShallowRef, onUnmounted, ref, shallowRef } from 'vue'

import { arrayBufferToBase64 } from '@/composables/kitty/kittyAgentAudioCodec'
import {
  KITTY_SCRIPT_PROCESSOR_BUFFER,
  type KittyMicGestureAssets,
  blessAudioContextSync,
  kickoffKittyMicGestureAssets,
  releaseKittyMicGestureAssets,
  resolveAudioContextConstructor,
  setMicTracksEnabled,
} from '@/composables/kitty/kittyMicGestureKickoff'
import { useKittySessionStore } from '@/stores/kittySession'

export type { KittyMicGestureAssets } from '@/composables/kitty/kittyMicGestureKickoff'
export {
  blessAudioContextSync,
  kickoffKittyMicGestureAssets,
  releaseKittyMicGestureAssets,
} from '@/composables/kitty/kittyMicGestureKickoff'

const TARGET_SAMPLE_RATE = 16000
const FRAME_SAMPLES = 1600
const WORKLET_NAME = 'kitty-fun-asr-pcm-processor'
const WORKLET_URL = '/kitty-fun-asr-pcm-processor.js'

export type KittyFunAsrStartFailure = 'not_connected' | 'mic_denied' | 'context_dead'
export type KittyFunAsrStartResult =
  | { ok: true; utteranceId: string }
  | { ok: false; reason: KittyFunAsrStartFailure }

function downsampleTo16k(input: Float32Array, inputRate: number): Int16Array {
  if (inputRate === TARGET_SAMPLE_RATE) {
    const out = new Int16Array(input.length)
    for (let i = 0; i < input.length; i += 1) {
      const s = Math.max(-1, Math.min(1, input[i] ?? 0))
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff
    }
    return out
  }
  const ratio = inputRate / TARGET_SAMPLE_RATE
  const outLength = Math.max(1, Math.floor(input.length / ratio))
  const out = new Int16Array(outLength)
  for (let i = 0; i < outLength; i += 1) {
    const idx = Math.floor(i * ratio)
    const s = Math.max(-1, Math.min(1, input[idx] ?? 0))
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return out
}

function nextUtteranceId(): string {
  return `utt_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
}

function isAudioContextUsable(ctx: AudioContext): boolean {
  const state = ctx.state as AudioContextState | 'interrupted'
  return state !== 'closed' && state !== 'interrupted'
}

function hasLiveMicTrack(stream: MediaStream): boolean {
  return stream.getAudioTracks().some((track) => track.readyState !== 'ended')
}

export function useKittyFunAsrMic(options: {
  ws: ShallowRef<WebSocket | null>
  stopPlayback: () => void
  languageHints?: Ref<string[] | undefined>
  ensureConnected?: () => Promise<boolean>
  onError?: (code: KittyFunAsrStartFailure) => void
}) {
  const kittySession = useKittySessionStore()
  const listening = ref(false)
  const activeUtteranceId = ref<string | null>(null)
  const audioContext = shallowRef<AudioContext | null>(null)
  const micStream = shallowRef<MediaStream | null>(null)
  const workletNode = shallowRef<AudioWorkletNode | null>(null)
  const scriptProcessor = shallowRef<ScriptProcessorNode | null>(null)
  const source = shallowRef<MediaStreamAudioSourceNode | null>(null)
  const silentGain = shallowRef<GainNode | null>(null)
  const debugCtxState = ref('none')
  const debugFramesSent = ref(0)
  const debugLastError = ref('')
  let pcmBuffer = new Int16Array(0)
  let warmReady = false
  let warmInFlight: Promise<boolean> | null = null
  /** Invalidates pending getUserMedia adoption after teardown. */
  let acquisitionGeneration = 0

  function refreshDebugCtxState(): void {
    const ctx = audioContext.value
    debugCtxState.value = ctx ? ctx.state : 'none'
  }

  function sendJson(payload: Record<string, unknown>): boolean {
    const socket = options.ws.value
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return false
    }
    try {
      socket.send(JSON.stringify(payload))
      return true
    } catch {
      return false
    }
  }

  function appendPcm(input: Float32Array, inputRate: number): void {
    if (!listening.value) {
      return
    }
    const samples = new Float32Array(input)
    const pcm = downsampleTo16k(samples, inputRate)
    const merged = new Int16Array(pcmBuffer.length + pcm.length)
    merged.set(pcmBuffer)
    merged.set(pcm, pcmBuffer.length)
    pcmBuffer = merged
    flushPcm(false)
  }

  function flushPcm(force = false): void {
    const utteranceId = activeUtteranceId.value
    while (pcmBuffer.length >= FRAME_SAMPLES || (force && pcmBuffer.length > 0)) {
      const take = force ? Math.min(FRAME_SAMPLES, pcmBuffer.length) : FRAME_SAMPLES
      const frame = pcmBuffer.slice(0, take)
      pcmBuffer = pcmBuffer.slice(take)
      const payload: Record<string, unknown> = {
        type: 'asr_audio',
        data: arrayBufferToBase64(
          frame.buffer.slice(frame.byteOffset, frame.byteOffset + frame.byteLength)
        ),
      }
      if (utteranceId) {
        payload.utterance_id = utteranceId
      }
      if (sendJson(payload)) {
        debugFramesSent.value += 1
      }
      if (force && pcmBuffer.length === 0) {
        break
      }
    }
  }

  function teardownCaptureNodesOnly(): void {
    if (workletNode.value) {
      workletNode.value.port.onmessage = null
      try {
        workletNode.value.disconnect()
      } catch {
        /* ignore */
      }
      workletNode.value = null
    }
    if (scriptProcessor.value) {
      scriptProcessor.value.onaudioprocess = null
      try {
        scriptProcessor.value.disconnect()
      } catch {
        /* ignore */
      }
      scriptProcessor.value = null
    }
    if (silentGain.value) {
      try {
        silentGain.value.disconnect()
      } catch {
        /* ignore */
      }
      silentGain.value = null
    }
    if (source.value) {
      try {
        source.value.disconnect()
      } catch {
        /* ignore */
      }
      source.value = null
    }
  }

  function teardownWarmMic(): void {
    acquisitionGeneration += 1
    listening.value = false
    activeUtteranceId.value = null
    kittySession.setAsrListening(false)
    teardownCaptureNodesOnly()
    if (micStream.value) {
      micStream.value.getTracks().forEach((track) => track.stop())
      micStream.value = null
    }
    if (audioContext.value && audioContext.value.state !== 'closed') {
      void audioContext.value.close()
    }
    audioContext.value = null
    warmReady = false
    warmInFlight = null
    pcmBuffer = new Int16Array(0)
    refreshDebugCtxState()
  }

  function connectSilentTap(
    ctx: AudioContext,
    mediaSource: MediaStreamAudioSourceNode,
    node: AudioNode
  ): GainNode {
    const mute = ctx.createGain()
    // Safari can suspend graphs with exact zero gain; keep a near-silent tap.
    mute.gain.value = 0.001
    mediaSource.connect(node)
    node.connect(mute)
    mute.connect(ctx.destination)
    return mute
  }

  async function startWorkletCapture(ctx: AudioContext, stream: MediaStream): Promise<boolean> {
    try {
      await ctx.audioWorklet.addModule(WORKLET_URL)
      const mediaSource = ctx.createMediaStreamSource(stream)
      const node = new AudioWorkletNode(ctx, WORKLET_NAME)
      node.port.onmessage = (event: MessageEvent) => {
        const data = event.data as {
          type?: string
          sampleRate?: number
          buffer?: ArrayBuffer
        }
        if (data?.type !== 'samples' || !(data.buffer instanceof ArrayBuffer)) {
          return
        }
        const rate =
          typeof data.sampleRate === 'number' && data.sampleRate > 0
            ? data.sampleRate
            : ctx.sampleRate
        appendPcm(new Float32Array(data.buffer), rate)
      }
      const mute = connectSilentTap(ctx, mediaSource, node)
      micStream.value = stream
      audioContext.value = ctx
      source.value = mediaSource
      workletNode.value = node
      silentGain.value = mute
      return true
    } catch {
      return false
    }
  }

  function startScriptProcessorCapture(ctx: AudioContext, stream: MediaStream): void {
    const mediaSource = ctx.createMediaStreamSource(stream)
    const script = ctx.createScriptProcessor(KITTY_SCRIPT_PROCESSOR_BUFFER, 1, 1)
    script.onaudioprocess = (event) => {
      appendPcm(event.inputBuffer.getChannelData(0), ctx.sampleRate)
    }
    const mute = connectSilentTap(ctx, mediaSource, script)
    micStream.value = stream
    audioContext.value = ctx
    source.value = mediaSource
    scriptProcessor.value = script
    silentGain.value = mute
  }

  function adoptGestureCapture(assets: KittyMicGestureAssets): void {
    const ctx = assets.audioContext
    assets.scriptProcessor.onaudioprocess = (event) => {
      appendPcm(event.inputBuffer.getChannelData(0), ctx.sampleRate)
    }
    micStream.value = assets.stream
    audioContext.value = ctx
    source.value = assets.mediaSource
    scriptProcessor.value = assets.scriptProcessor
    silentGain.value = assets.silentGain
    warmReady = true
    setMicTracksEnabled(assets.stream, false)
    refreshDebugCtxState()
  }

  function invalidateWarmCapture(): void {
    teardownCaptureNodesOnly()
    if (micStream.value) {
      micStream.value.getTracks().forEach((track) => track.stop())
      micStream.value = null
    }
    if (audioContext.value && audioContext.value.state !== 'closed') {
      void audioContext.value.close()
    }
    audioContext.value = null
    warmReady = false
    refreshDebugCtxState()
  }

  function isWarmCaptureHealthy(): boolean {
    const ctx = audioContext.value
    const stream = micStream.value
    if (!warmReady || !ctx || !stream) {
      return false
    }
    return isAudioContextUsable(ctx) && hasLiveMicTrack(stream)
  }

  /** Sync entry from an activation-capable call stack (see kittyWebKitUserActivation). */
  function prepareMicFromUserGesture(): Promise<boolean> {
    if (isWarmCaptureHealthy() && audioContext.value) {
      blessAudioContextSync(audioContext.value)
      refreshDebugCtxState()
      return Promise.resolve(true)
    }
    if (warmReady) {
      invalidateWarmCapture()
    }
    if (warmInFlight) {
      return warmInFlight
    }
    const generation = acquisitionGeneration
    warmInFlight = (async () => {
      try {
        const assets = await kickoffKittyMicGestureAssets()
        if (generation !== acquisitionGeneration) {
          releaseKittyMicGestureAssets(assets)
          return false
        }
        adoptGestureCapture(assets)
        debugLastError.value = ''
        return true
      } catch {
        debugLastError.value = 'mic_denied'
        options.onError?.('mic_denied')
        return false
      } finally {
        warmInFlight = null
        refreshDebugCtxState()
      }
    })()
    return warmInFlight
  }

  /**
   * Re-bless an existing AudioContext inside an activation-triggering handler
   * (touch pointerup / touchend / keydown / mouse pointerdown).
   */
  function blessFromUserActivation(): void {
    const ctx = audioContext.value
    if (!ctx || ctx.state === 'closed') {
      return
    }
    blessAudioContextSync(ctx)
    refreshDebugCtxState()
  }

  async function ensureCaptureGraph(): Promise<boolean> {
    if (isWarmCaptureHealthy() && micStream.value && audioContext.value) {
      if (audioContext.value.state === 'suspended') {
        blessAudioContextSync(audioContext.value)
        // iOS can leave resume() pending forever — never block PTT on it.
        await Promise.race([
          audioContext.value.resume().catch(() => undefined),
          new Promise<void>((resolve) => {
            setTimeout(resolve, 400)
          }),
        ])
      }
      refreshDebugCtxState()
      return isWarmCaptureHealthy()
    }
    if (warmReady) {
      invalidateWarmCapture()
    }
    const warmed = await prepareMicFromUserGesture()
    if (warmed && isWarmCaptureHealthy()) {
      return true
    }
    // Desktop toggle cold path (no prior pointerdown warm)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })
      const AudioCtx = resolveAudioContextConstructor()
      const ctx = new AudioCtx()
      blessAudioContextSync(ctx)
      if (ctx.state === 'suspended') {
        await Promise.race([
          ctx.resume().catch(() => undefined),
          new Promise<void>((resolve) => {
            setTimeout(resolve, 400)
          }),
        ])
      }
      const workletOk = await startWorkletCapture(ctx, stream)
      if (!workletOk) {
        startScriptProcessorCapture(ctx, stream)
      }
      warmReady = true
      setMicTracksEnabled(stream, false)
      refreshDebugCtxState()
      return true
    } catch {
      debugLastError.value = 'mic_denied'
      options.onError?.('mic_denied')
      return false
    }
  }

  async function startListening(
    gestureAssets?: KittyMicGestureAssets
  ): Promise<KittyFunAsrStartResult> {
    if (listening.value) {
      if (gestureAssets) {
        releaseKittyMicGestureAssets(gestureAssets)
      }
      const existing = activeUtteranceId.value
      if (existing) {
        return { ok: true, utteranceId: existing }
      }
      return { ok: false, reason: 'not_connected' }
    }
    // Only reconnect when the socket is not already open. Re-entering
    // startConversation during PTT can hang the hold and skip asr_start.
    if (
      options.ensureConnected &&
      (!options.ws.value || options.ws.value.readyState !== WebSocket.OPEN)
    ) {
      const ok = await options.ensureConnected()
      if (!ok) {
        if (gestureAssets) {
          releaseKittyMicGestureAssets(gestureAssets)
        }
        debugLastError.value = 'not_connected'
        options.onError?.('not_connected')
        return { ok: false, reason: 'not_connected' }
      }
    }
    if (!options.ws.value || options.ws.value.readyState !== WebSocket.OPEN) {
      if (gestureAssets) {
        releaseKittyMicGestureAssets(gestureAssets)
      }
      debugLastError.value = 'not_connected'
      options.onError?.('not_connected')
      return { ok: false, reason: 'not_connected' }
    }

    options.stopPlayback()
    sendJson({ type: 'tts_interrupt' })

    if (gestureAssets) {
      adoptGestureCapture(gestureAssets)
    } else {
      const ok = await ensureCaptureGraph()
      if (!ok) {
        return { ok: false, reason: 'mic_denied' }
      }
    }

    if (!micStream.value || !audioContext.value || !isWarmCaptureHealthy()) {
      debugLastError.value = 'context_dead'
      options.onError?.('context_dead')
      return { ok: false, reason: 'context_dead' }
    }

    // Send asr_start even if context is still suspended — capturing unlock /
    // later activation-triggering bless may start PCM; server must see the hold.
    const utteranceId = nextUtteranceId()
    blessAudioContextSync(audioContext.value)
    setMicTracksEnabled(micStream.value, true)
    debugFramesSent.value = 0
    listening.value = true
    activeUtteranceId.value = utteranceId
    kittySession.setAsrListening(true)
    refreshDebugCtxState()

    const hints = options.languageHints?.value
    if (
      !sendJson({
        type: 'asr_start',
        utterance_id: utteranceId,
        language_hints: hints && hints.length > 0 ? hints : ['zh'],
        debug_ctx: audioContext.value.state,
      })
    ) {
      listening.value = false
      activeUtteranceId.value = null
      kittySession.setAsrListening(false)
      setMicTracksEnabled(micStream.value, false)
      debugLastError.value = 'not_connected'
      options.onError?.('not_connected')
      return { ok: false, reason: 'not_connected' }
    }
    return { ok: true, utteranceId }
  }

  function stopListening(): void {
    const utteranceId = activeUtteranceId.value
    if (!listening.value) {
      if (micStream.value) {
        setMicTracksEnabled(micStream.value, false)
      }
      return
    }
    listening.value = false
    flushPcm(true)
    const payload: Record<string, unknown> = { type: 'asr_stop' }
    if (utteranceId) {
      payload.utterance_id = utteranceId
    }
    sendJson(payload)
    activeUtteranceId.value = null
    kittySession.setAsrListening(false)
    if (micStream.value) {
      setMicTracksEnabled(micStream.value, false)
    }
    refreshDebugCtxState()
  }

  async function toggleListening(): Promise<void> {
    if (listening.value) {
      stopListening()
      return
    }
    await startListening()
  }

  onUnmounted(() => {
    stopListening()
    teardownWarmMic()
  })

  return {
    listening,
    activeUtteranceId,
    debugCtxState,
    debugFramesSent,
    debugLastError,
    prepareMicFromUserGesture,
    blessFromUserActivation,
    startListening,
    stopListening,
    toggleListening,
    teardownWarmMic,
  }
}
