/**
 * Live translation subtitles (DashScope qwen3-livetranslate-flash-realtime).
 * Translation arrives as completed sentence blocks (response.text.done) — no interim streaming.
 * Shares the same overlay component as live subtitles.
 */
import { ref, shallowRef } from 'vue'

import { defineStore } from 'pinia'

import { useNotifications } from '@/composables/core/useNotifications'
import { i18n } from '@/i18n'
import { useUIStore } from '@/stores/ui'

const TARGET_SAMPLE_RATE = 16000
const SCRIPT_PROCESS_BUFFER_SIZE = 2048

/** Maximum committed lines kept in memory — oldest are dropped automatically. */
const MAX_COMMITTED_LINES = 100

function buildTranslateWebSocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/ws/canvas-translate`
}

/**
 * Map prompt language → ASR source language code.
 * Reuse the same mapping as the subtitles store.
 */
function mapPromptLanguageToSource(lang: string): string {
  const lower = (lang || 'en').toLowerCase()
  if (
    lower.includes('yue') ||
    lower.includes('-hk') ||
    lower.endsWith('hk') ||
    lower === 'zh-hant-hk'
  ) {
    return 'yue'
  }
  const base = lower.split('-')[0]?.toLowerCase() || 'en'
  const map: Record<string, string> = {
    zh: 'zh', yue: 'yue', en: 'en', ja: 'ja', ko: 'ko', de: 'de',
    fr: 'fr', es: 'es', ru: 'ru', ar: 'ar', pt: 'pt', it: 'it',
    hi: 'hi', id: 'id', th: 'th', tr: 'tr', uk: 'uk', vi: 'vi',
    cs: 'cs', da: 'da', fil: 'fil', fi: 'fi', is: 'is', ms: 'ms',
    no: 'no', pl: 'pl', sv: 'sv',
  }
  return map[base] ?? 'en'
}

/**
 * Derive translation target language from the source.
 * Default rule: zh/yue → en, anything else → zh.
 */
function deriveTargetLanguage(sourceLang: string): string {
  if (sourceLang === 'zh' || sourceLang === 'yue') return 'en'
  return 'zh'
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  let binary = ''
  const bytes = new Uint8Array(buffer)
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return window.btoa(binary)
}

function float32ToPcm16Base64(input: Float32Array, inputRate: number): string {
  if (inputRate === TARGET_SAMPLE_RATE) {
    const pcm = new Int16Array(input.length)
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i]))
      pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff
    }
    return arrayBufferToBase64(pcm.buffer)
  }
  const ratio = inputRate / TARGET_SAMPLE_RATE
  const outLen = Math.floor(input.length / ratio)
  const pcm = new Int16Array(outLen)
  for (let i = 0; i < outLen; i++) {
    const start = Math.floor(i * ratio)
    const end = Math.min(Math.floor((i + 1) * ratio), input.length)
    let sum = 0
    for (let j = start; j < end; j++) {
      sum += input[j] as number
    }
    const avg = sum / (end - start)
    const s = Math.max(-1, Math.min(1, avg))
    pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return arrayBufferToBase64(pcm.buffer)
}

function nextEventId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `evt_${crypto.randomUUID().replace(/-/g, '')}`
  }
  return `evt_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 11)}`
}

export const useLiveTranslationStore = defineStore('liveTranslation', () => {
  const uiStore = useUIStore()
  const notify = useNotifications()

  const enabled = ref(false)
  const connecting = ref(false)

  /**
   * Monotonically-increasing stamp incremented each time enable() is called.
   * Captured in the socket.onclose closure so stale close events from a previous
   * session cannot inadvertently tear down a newly-started one.
   */
  let currentSessionStamp = 0

  /**
   * User-selected target language code, or 'auto' to derive from the UI prompt language.
   * Persists across toggle cycles within the same session.
   */
  const targetLanguage = ref<string>('auto')

  /**
   * Completed translation sentences, newest last.
   * Capped at MAX_COMMITTED_LINES to prevent unbounded memory growth.
   */
  const committedLines = ref<string[]>([])

  /**
   * Currently streaming sentence from response.text.text (confirmed text + stash).
   * Cleared when response.text.done arrives and the line is committed.
   */
  const interimText = ref<string>('')

  const wsRef = shallowRef<WebSocket | null>(null)
  const audioContextRef = shallowRef<AudioContext | null>(null)
  const micStreamRef = shallowRef<MediaStream | null>(null)
  const processorRef = shallowRef<ScriptProcessorNode | null>(null)
  const mediaSourceRef = shallowRef<MediaStreamAudioSourceNode | null>(null)

  /** Unregister handle for the visibilitychange listener. */
  let removeVisibilityListener: (() => void) | null = null

  function translate(key: string): string {
    return i18n.global.t(key) as string
  }

  function stopMicrophoneGraph(): void {
    if (processorRef.value) {
      try { processorRef.value.disconnect() } catch { /* ignore */ }
      processorRef.value.onaudioprocess = null
      processorRef.value = null
    }
    if (mediaSourceRef.value) {
      try { mediaSourceRef.value.disconnect() } catch { /* ignore */ }
      mediaSourceRef.value = null
    }
    if (micStreamRef.value) {
      micStreamRef.value.getTracks().forEach((t) => t.stop())
      micStreamRef.value = null
    }
    const ctx = audioContextRef.value
    if (ctx && ctx.state !== 'closed') {
      void ctx.close().catch(() => {})
    }
    audioContextRef.value = null
  }

  function closeSocket(): void {
    const sock = wsRef.value
    wsRef.value = null
    if (!sock) return
    try { sock.close() } catch { /* ignore */ }
  }

  function unregisterVisibilityListener(): void {
    if (removeVisibilityListener) {
      removeVisibilityListener()
      removeVisibilityListener = null
    }
  }

  /**
   * Resume AudioContext when the tab becomes visible again.
   * Browsers suspend AudioContext on tab hide — without this, audio stops sending.
   */
  function registerVisibilityListener(): void {
    unregisterVisibilityListener()
    const handler = () => {
      const ctx = audioContextRef.value
      if (!ctx || ctx.state === 'closed') return
      if (document.visibilityState === 'visible' && ctx.state === 'suspended') {
        void ctx.resume().catch(() => {})
      }
    }
    document.addEventListener('visibilitychange', handler)
    removeVisibilityListener = () => document.removeEventListener('visibilitychange', handler)
  }

  function handleServerPayload(data: Record<string, unknown>): void {
    const typ = data.type as string

    // Streaming delta — show text forming live (confirmed text + speculative stash)
    if (typ === 'response.text.text') {
      const confirmed = String(data.text ?? '')
      const stash = String(data.stash ?? '')
      interimText.value = (confirmed + stash).trimStart()
      return
    }

    // Sentence complete — commit to captions, clear interim
    if (typ === 'response.text.done') {
      const line = String(data.text ?? '').trim()
      if (line.length > 0) {
        const next = [...committedLines.value, line]
        committedLines.value = next.length > MAX_COMMITTED_LINES
          ? next.slice(-MAX_COMMITTED_LINES)
          : next
      }
      interimText.value = ''
      return
    }

    // Audio+text mode fallback: transcript done
    if (typ === 'response.audio_transcript.done') {
      const line = String(data.transcript ?? '').trim()
      if (line.length > 0) {
        const next = [...committedLines.value, line]
        committedLines.value = next.length > MAX_COMMITTED_LINES
          ? next.slice(-MAX_COMMITTED_LINES)
          : next
      }
      interimText.value = ''
      return
    }

    if (typ === 'error') {
      const nested = data.error as { message?: string } | undefined
      const msg = String(
        nested?.message ??
          (data as { message?: string }).message ??
          translate('canvas.translation.genericError'),
      )
      notify.warning(msg)
    }
  }

  async function startMicrophoneAndAttach(): Promise<void> {
    const AudioCtx =
      window.AudioContext ||
      (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AudioCtx) throw new Error('AudioContext not supported')

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, sampleRate: TARGET_SAMPLE_RATE },
    })

    if (!enabled.value) {
      stream.getTracks().forEach((t) => t.stop())
      return
    }

    const ctx = new AudioCtx()
    audioContextRef.value = ctx
    micStreamRef.value = stream

    if (!enabled.value) {
      stream.getTracks().forEach((t) => t.stop())
      micStreamRef.value = null
      void ctx.close().catch(() => {})
      audioContextRef.value = null
      return
    }

    if (ctx.state === 'suspended') await ctx.resume()

    if (!enabled.value || ctx.state === 'closed') {
      stream.getTracks().forEach((t) => t.stop())
      micStreamRef.value = null
      void ctx.close().catch(() => {})
      audioContextRef.value = null
      return
    }

    const source = ctx.createMediaStreamSource(stream)
    mediaSourceRef.value = source

    const processor = ctx.createScriptProcessor(SCRIPT_PROCESS_BUFFER_SIZE, 1, 1)
    processorRef.value = processor

    processor.onaudioprocess = (event: AudioProcessingEvent) => {
      const sock = wsRef.value
      if (!sock || sock.readyState !== WebSocket.OPEN) return
      const inputData = event.inputBuffer.getChannelData(0)
      const audioB64 = float32ToPcm16Base64(inputData, ctx.sampleRate)
      try {
        sock.send(
          JSON.stringify({
            event_id: nextEventId(),
            type: 'input_audio_buffer.append',
            audio: audioB64,
          }),
        )
      } catch { /* ignore */ }
    }

    if (!enabled.value || (ctx.state as string) === 'closed') {
      stopMicrophoneGraph()
      return
    }

    source.connect(processor)
    processor.connect(ctx.destination)

    registerVisibilityListener()
  }

  function enable(): void {
    if (enabled.value || connecting.value) return
    if (!navigator.mediaDevices?.getUserMedia) {
      notify.warning(translate('canvas.translation.micUnavailable'))
      return
    }

    connecting.value = true
    committedLines.value = []
    interimText.value = ''

    const sessionStamp = ++currentSessionStamp
    const sourceLang = mapPromptLanguageToSource(String(uiStore.promptLanguage))
    const targetLang = targetLanguage.value === 'auto'
      ? deriveTargetLanguage(sourceLang)
      : targetLanguage.value

    const socket = new WebSocket(buildTranslateWebSocketUrl())
    wsRef.value = socket

    socket.onopen = () => {
      connecting.value = false
      enabled.value = true
      try {
        socket.send(
          JSON.stringify({
            type: 'start',
            source_language: sourceLang,
            target_language: targetLang,
          }),
        )
      } catch {
        notify.warning(translate('canvas.translation.wsError'))
        enabled.value = false
        connecting.value = false
        closeSocket()
        return
      }

      void startMicrophoneAndAttach().catch(() => {
        notify.warning(translate('canvas.translation.micFailed'))
        enabled.value = false
        closeSocket()
        stopMicrophoneGraph()
      })
    }

    socket.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string) as Record<string, unknown>
        handleServerPayload(data)
      } catch { /* ignore non-JSON */ }
    }

    socket.onerror = () => {
      if (connecting.value) connecting.value = false
      notify.warning(translate('canvas.translation.wsError'))
    }

    socket.onclose = () => {
      // Ignore stale close events from a previous session that has already
      // been replaced by a new enable() call.
      if (sessionStamp !== currentSessionStamp) return
      connecting.value = false
      enabled.value = false
      unregisterVisibilityListener()
      stopMicrophoneGraph()
      wsRef.value = null
    }
  }

  function disable(): void {
    enabled.value = false
    connecting.value = false
    interimText.value = ''
    unregisterVisibilityListener()
    stopMicrophoneGraph()
    closeSocket()
  }

  function toggle(): void {
    if (enabled.value || connecting.value) {
      disable()
    } else {
      enable()
    }
  }

  function setTargetLanguage(lang: string): void {
    targetLanguage.value = lang
  }

  return {
    enabled,
    connecting,
    targetLanguage,
    committedLines,
    interimText,
    enable,
    disable,
    toggle,
    setTargetLanguage,
  }
})
