/**
 * Fun-ASR mic capture for Kitty one-sentence panel (PCM 16 kHz mono → Kitty WS).
 * Prefers AudioWorklet; falls back to ScriptProcessor only when Worklet is unavailable.
 *
 * iOS Safari: getUserMedia + AudioContext must be kicked off inside the user-gesture
 * turn (pointerdown). Call kickoffKittyMicGestureAssets() synchronously from the
 * handler, then pass the resolved assets into startListening().
 */
import { type Ref, type ShallowRef, onUnmounted, ref, shallowRef } from 'vue'

import { arrayBufferToBase64 } from '@/composables/kitty/kittyAgentAudioCodec'
import { useKittySessionStore } from '@/stores/kittySession'

const TARGET_SAMPLE_RATE = 16000
const FRAME_SAMPLES = 1600 // ~100 ms at 16 kHz
const WORKLET_NAME = 'kitty-fun-asr-pcm-processor'
/** Same-origin public asset — CSP blocks blob: worklets under script-src 'self'. */
const WORKLET_URL = '/kitty-fun-asr-pcm-processor.js'

export interface KittyMicGestureAssets {
  stream: MediaStream
  audioContext: AudioContext
}

/**
 * Start getUserMedia + AudioContext in the current call stack (user-gesture window).
 * Safe to await the returned promise after later async work (WS connect).
 */
export function kickoffKittyMicGestureAssets(): Promise<KittyMicGestureAssets> {
  if (!navigator.mediaDevices?.getUserMedia) {
    return Promise.reject(new Error('mic_unavailable'))
  }
  const streamPromise = navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  })
  const audioContext = new AudioContext()
  const resumePromise =
    audioContext.state === 'suspended' ? audioContext.resume() : Promise.resolve()
  return (async () => {
    try {
      const stream = await streamPromise
      await resumePromise
      return { stream, audioContext }
    } catch (err) {
      void audioContext.close()
      throw err
    }
  })()
}

export function releaseKittyMicGestureAssets(assets: KittyMicGestureAssets): void {
  assets.stream.getTracks().forEach((track) => track.stop())
  void assets.audioContext.close()
}

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

export function useKittyFunAsrMic(options: {
  ws: ShallowRef<WebSocket | null>
  stopPlayback: () => void
  languageHints?: Ref<string[] | undefined>
  /** Ensure Kitty WS is open before asr_start / asr_audio. */
  ensureConnected?: () => Promise<boolean>
  onError?: (code: 'not_connected' | 'mic_denied') => void
}) {
  const kittySession = useKittySessionStore()
  const listening = ref(false)
  const audioContext = shallowRef<AudioContext | null>(null)
  const micStream = shallowRef<MediaStream | null>(null)
  const workletNode = shallowRef<AudioWorkletNode | null>(null)
  const scriptProcessor = shallowRef<ScriptProcessorNode | null>(null)
  const source = shallowRef<MediaStreamAudioSourceNode | null>(null)
  const silentGain = shallowRef<GainNode | null>(null)
  let pcmBuffer = new Int16Array(0)

  function sendJson(payload: Record<string, unknown>): boolean {
    const socket = options.ws.value
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return false
    }
    socket.send(JSON.stringify(payload))
    return true
  }

  function appendPcm(input: Float32Array, inputRate: number): void {
    if (!listening.value) {
      return
    }
    const pcm = downsampleTo16k(input, inputRate)
    const merged = new Int16Array(pcmBuffer.length + pcm.length)
    merged.set(pcmBuffer)
    merged.set(pcm, pcmBuffer.length)
    pcmBuffer = merged
    flushPcm(false)
  }

  function flushPcm(force = false): void {
    while (pcmBuffer.length >= FRAME_SAMPLES || (force && pcmBuffer.length > 0)) {
      const take = force
        ? Math.min(FRAME_SAMPLES, pcmBuffer.length)
        : FRAME_SAMPLES
      const frame = pcmBuffer.slice(0, take)
      pcmBuffer = pcmBuffer.slice(take)
      sendJson({
        type: 'asr_audio',
        data: arrayBufferToBase64(
          frame.buffer.slice(frame.byteOffset, frame.byteOffset + frame.byteLength)
        ),
      })
      if (force && pcmBuffer.length === 0) {
        break
      }
    }
  }

  function teardownCapture(): void {
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
    if (micStream.value) {
      micStream.value.getTracks().forEach((track) => track.stop())
      micStream.value = null
    }
    if (audioContext.value) {
      void audioContext.value.close()
      audioContext.value = null
    }
    pcmBuffer = new Int16Array(0)
  }

  function connectSilentTap(
    ctx: AudioContext,
    mediaSource: MediaStreamAudioSourceNode,
    node: AudioNode
  ): GainNode {
    const mute = ctx.createGain()
    mute.gain.value = 0
    mediaSource.connect(node)
    node.connect(mute)
    mute.connect(ctx.destination)
    return mute
  }

  async function startWorkletCapture(
    ctx: AudioContext,
    stream: MediaStream
  ): Promise<boolean> {
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
    const script = ctx.createScriptProcessor(4096, 1, 1)
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

  async function startListening(gestureAssets?: KittyMicGestureAssets): Promise<void> {
    if (listening.value) {
      if (gestureAssets) {
        releaseKittyMicGestureAssets(gestureAssets)
      }
      return
    }
    if (options.ensureConnected) {
      const ok = await options.ensureConnected()
      if (!ok) {
        if (gestureAssets) {
          releaseKittyMicGestureAssets(gestureAssets)
        }
        return
      }
    }
    if (!options.ws.value || options.ws.value.readyState !== WebSocket.OPEN) {
      if (gestureAssets) {
        releaseKittyMicGestureAssets(gestureAssets)
      }
      options.onError?.('not_connected')
      return
    }

    options.stopPlayback()
    sendJson({ type: 'tts_interrupt' })

    let stream: MediaStream
    let ctx: AudioContext
    if (gestureAssets) {
      stream = gestureAssets.stream
      ctx = gestureAssets.audioContext
    } else {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
          },
        })
      } catch {
        options.onError?.('mic_denied')
        return
      }
      ctx = new AudioContext()
    }
    if (ctx.state === 'suspended') {
      await ctx.resume()
    }

    const workletOk = await startWorkletCapture(ctx, stream)
    if (!workletOk) {
      startScriptProcessorCapture(ctx, stream)
    }

    listening.value = true
    kittySession.setAsrListening(true)

    const hints = options.languageHints?.value
    if (
      !sendJson({
        type: 'asr_start',
        language_hints: hints && hints.length > 0 ? hints : ['zh'],
      })
    ) {
      listening.value = false
      kittySession.setAsrListening(false)
      teardownCapture()
      options.onError?.('not_connected')
    }
  }

  function stopListening(): void {
    if (!listening.value) {
      return
    }
    listening.value = false
    flushPcm(true)
    sendJson({ type: 'asr_stop' })
    kittySession.setAsrListening(false)
    teardownCapture()
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
  })

  return {
    listening,
    startListening,
    stopListening,
    toggleListening,
  }
}
