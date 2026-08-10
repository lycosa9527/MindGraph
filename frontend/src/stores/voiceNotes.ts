/**
 * Voice Notes — Fun-ASR realtime → Document Summary markdown.
 *
 * Session stoppers: max 60m duration, 2m silence auto-stop, mic lost,
 * WS drop / auth fail / started timeout, pagehide. Soft pause freezes silence.
 */
import { computed, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'

import { defineStore } from 'pinia'

import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { useNotifications } from '@/composables/core/useNotifications'
import {
  DOC_SUMMARY_API_BASE,
  DOC_SUMMARY_MAX_INPUT_CHARS,
  DOC_SUMMARY_PACKAGES_BASE,
} from '@/config/docSummaryApi'
import { i18n } from '@/i18n'
import {
  useAuthStore,
  useKittySessionStore,
  useLiveSubtitlesStore,
  useSavedDiagramsStore,
  useUIStore,
} from '@/stores'
import { useLiveTranslationStore } from '@/stores/liveTranslation'
import { getDefaultTemplate } from '@/stores/specLoader'
import { apiRequestJson } from '@/utils/apiClient'
import {
  VOICE_NOTES_SPEECH_RMS_THRESHOLD,
  VOICE_NOTES_TARGET_SAMPLE_RATE,
  float32Rms,
  float32ToPcm16Base64,
} from '@/utils/voiceNotesAudio'

const SCRIPT_PROCESS_BUFFER_SIZE = 2048
const MAX_COMMITTED_LINES = 500
/** Hard session cap. */
const MAX_SESSION_MS = 60 * 60 * 1000
/** Auto-stop when no speech energy / ASR text for this long (active recording only). */
const SILENCE_AUTO_STOP_MS = 2 * 60 * 1000
const SILENCE_CHECK_MS = 5_000
/** Wait for server ``started`` after WS open. */
const STARTED_TIMEOUT_MS = 15_000

export type VoiceNotesStopReason =
  | 'user'
  | 'silence'
  | 'max_duration'
  | 'mic_lost'
  | 'ws_error'
  | 'ws_closed'
  | 'auth'
  | 'started_timeout'
  | 'upstream_error'
  | 'pagehide'
  | 'exit'

type DocSummaryPackage = {
  id: number
  diagram_id?: string | null
  title?: string | null
}

function buildVoiceNotesWebSocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/ws/voice-notes`
}

function mapPromptLanguageToHints(lang: string): string[] {
  const lower = (lang || 'zh').toLowerCase()
  const base = lower.split('-')[0] || 'zh'
  if (base === 'zh' || base === 'yue') return ['zh']
  if (base === 'en') return ['en']
  if (base === 'ja') return ['ja']
  return ['zh', 'en']
}

function formatVoiceNoteTitle(date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `voice recording_${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
    `${pad(date.getHours())}${pad(date.getMinutes())}`
  )
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

export const useVoiceNotesStore = defineStore('voiceNotes', () => {
  const router = useRouter()
  const notify = useNotifications()
  const uiStore = useUIStore()
  const authStore = useAuthStore()
  const savedDiagramsStore = useSavedDiagramsStore()

  const enabled = ref(false)
  const bootstrapping = ref(false)
  const modalOpen = ref(false)
  const recording = ref(false)
  const paused = ref(false)
  const connecting = ref(false)
  const ingesting = ref(false)
  const stopping = ref(false)
  const lines = ref<string[]>([])
  const liveText = ref('')
  const elapsedMs = ref(0)
  const packageId = ref<number | null>(null)
  const diagramId = ref<string | null>(null)
  const error = ref<string | null>(null)
  const lastStopReason = ref<VoiceNotesStopReason | null>(null)
  const sessionReady = ref(false)
  /** Smoothed mic level 0–1 for FAB volume wave (active recording only). */
  const inputLevel = ref(0)

  let currentSessionStamp = 0
  let removeVisibilityListener: (() => void) | null = null
  let removePageHideListener: (() => void) | null = null
  let removeTrackEndedListener: (() => void) | null = null
  let elapsedTimer: number | null = null
  let maxDurationTimer: number | null = null
  let silenceCheckTimer: number | null = null
  let startedTimeoutTimer: number | null = null
  let recordingStartedAt = 0
  let pausedAccumulatedMs = 0
  let lastSpeechAt = 0
  let intentionalClose = false
  let bootstrapPromise: Promise<boolean> | null = null
  let smoothedInputLevel = 0
  let lastInputLevelUiAt = 0

  const wsRef = shallowRef<WebSocket | null>(null)
  const audioContextRef = shallowRef<AudioContext | null>(null)
  const micStreamRef = shallowRef<MediaStream | null>(null)
  const processorRef = shallowRef<ScriptProcessorNode | null>(null)
  const mediaSourceRef = shallowRef<MediaStreamAudioSourceNode | null>(null)

  const transcriptText = computed(() => {
    const committed = lines.value.filter((s) => s.trim().length > 0)
    const live = liveText.value.trim()
    if (!live) return committed.join('\n')
    if (committed.length === 0) return live
    return `${committed.join('\n')}\n${live}`
  })

  const hasActiveCapture = computed(() => recording.value || paused.value)

  const sessionStatus = computed(() => {
    if (ingesting.value) return 'ingesting'
    if (stopping.value) return 'stopping'
    if (connecting.value) return 'connecting'
    if (paused.value) return 'paused'
    if (recording.value && sessionReady.value) return 'recording'
    if (recording.value) return 'starting'
    return 'idle'
  })

  function t(key: string): string {
    return i18n.global.t(key) as string
  }

  function openModal(): void {
    modalOpen.value = true
  }

  function closeModal(): void {
    modalOpen.value = false
  }

  function markSpeechActivity(): void {
    lastSpeechAt = Date.now()
  }

  function resetInputLevel(): void {
    smoothedInputLevel = 0
    lastInputLevelUiAt = 0
    inputLevel.value = 0
  }

  /** Map RMS → 0–1 and publish a smoothed level for the FAB (~30 fps). */
  function publishInputLevel(rms: number): void {
    const instant = Math.min(1, Math.max(0, rms / 0.18))
    smoothedInputLevel = smoothedInputLevel * 0.72 + instant * 0.28
    const now = Date.now()
    if (now - lastInputLevelUiAt < 32 && instant < 0.95) return
    lastInputLevelUiAt = now
    inputLevel.value = smoothedInputLevel
  }

  function clearWatchTimers(): void {
    if (elapsedTimer !== null) {
      window.clearInterval(elapsedTimer)
      elapsedTimer = null
    }
    if (maxDurationTimer !== null) {
      window.clearTimeout(maxDurationTimer)
      maxDurationTimer = null
    }
    if (silenceCheckTimer !== null) {
      window.clearInterval(silenceCheckTimer)
      silenceCheckTimer = null
    }
    if (startedTimeoutTimer !== null) {
      window.clearTimeout(startedTimeoutTimer)
      startedTimeoutTimer = null
    }
  }

  function startSessionWatchers(): void {
    clearWatchTimers()
    recordingStartedAt = Date.now()
    pausedAccumulatedMs = 0
    elapsedMs.value = 0
    markSpeechActivity()

    elapsedTimer = window.setInterval(() => {
      if (!recording.value || paused.value) return
      elapsedMs.value = pausedAccumulatedMs + (Date.now() - recordingStartedAt)
    }, 250)

    maxDurationTimer = window.setTimeout(() => {
      notify.warning(t('auth.voiceNotes.maxDuration'))
      void stopRecording('max_duration')
    }, MAX_SESSION_MS)

    silenceCheckTimer = window.setInterval(() => {
      if (!recording.value || paused.value || stopping.value) return
      if (Date.now() - lastSpeechAt >= SILENCE_AUTO_STOP_MS) {
        notify.warning(t('auth.voiceNotes.silenceAutoStop'))
        void stopRecording('silence')
      }
    }, SILENCE_CHECK_MS)
  }

  function clearStartedTimeout(): void {
    if (startedTimeoutTimer !== null) {
      window.clearTimeout(startedTimeoutTimer)
      startedTimeoutTimer = null
    }
  }

  function armStartedTimeout(sessionStamp: number): void {
    clearStartedTimeout()
    startedTimeoutTimer = window.setTimeout(() => {
      if (sessionStamp !== currentSessionStamp) return
      if (sessionReady.value) return
      notify.warning(t('auth.voiceNotes.startedTimeout'))
      void abortSession('started_timeout')
    }, STARTED_TIMEOUT_MS)
  }

  async function ensureMindmapSession(): Promise<boolean> {
    if (diagramId.value && packageId.value) return true
    if (bootstrapPromise) return bootstrapPromise

    bootstrapPromise = (async () => {
      bootstrapping.value = true
      error.value = null
      try {
        const lang = String(uiStore.promptLanguage || uiStore.language || 'zh').split('-')[0] || 'zh'
        const template = getDefaultTemplate('mindmap', uiStore.language)
        if (!template) {
          notify.warning(t('auth.voiceNotes.bootstrapFailed'))
          return false
        }
        const title = formatVoiceNoteTitle()
        const saved = await savedDiagramsStore.saveDiagram(title, 'mindmap', template, lang)
        if (!saved?.id) {
          notify.warning(t('auth.voiceNotes.saveFailed'))
          return false
        }
        const pkgId = await ensureDocSummaryPackage(saved.id, title)
        diagramId.value = saved.id
        packageId.value = pkgId
        return true
      } catch (exc) {
        const msg = exc instanceof Error ? exc.message : t('auth.voiceNotes.bootstrapFailed')
        error.value = msg
        notify.warning(msg)
        return false
      } finally {
        bootstrapping.value = false
        bootstrapPromise = null
      }
    })()

    return bootstrapPromise
  }

  async function jumpToMindmap(): Promise<void> {
    const ok = await ensureMindmapSession()
    if (!ok || !diagramId.value) return
    await router.push({ path: '/canvas', query: { diagramId: diagramId.value } })
  }

  function unregisterVisibilityListener(): void {
    if (removeVisibilityListener) {
      removeVisibilityListener()
      removeVisibilityListener = null
    }
  }

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

  function unregisterPageHideListener(): void {
    if (removePageHideListener) {
      removePageHideListener()
      removePageHideListener = null
    }
  }

  function registerPageHideListener(): void {
    unregisterPageHideListener()
    const handler = () => {
      if (recording.value || paused.value) {
        void stopRecording('pagehide')
      }
    }
    window.addEventListener('pagehide', handler)
    removePageHideListener = () => window.removeEventListener('pagehide', handler)
  }

  function unregisterTrackEndedListener(): void {
    if (removeTrackEndedListener) {
      removeTrackEndedListener()
      removeTrackEndedListener = null
    }
  }

  function registerTrackEndedListener(stream: MediaStream): void {
    unregisterTrackEndedListener()
    const track = stream.getAudioTracks()[0]
    if (!track) return
    const onEnded = () => {
      if (!recording.value && !paused.value) return
      notify.warning(t('auth.voiceNotes.micLost'))
      void stopRecording('mic_lost')
    }
    track.addEventListener('ended', onEnded)
    removeTrackEndedListener = () => track.removeEventListener('ended', onEnded)
  }

  function stopMicrophoneGraph(): void {
    unregisterTrackEndedListener()
    if (processorRef.value) {
      try {
        processorRef.value.disconnect()
      } catch {
        /* ignore */
      }
      processorRef.value.onaudioprocess = null
      processorRef.value = null
    }
    if (mediaSourceRef.value) {
      try {
        mediaSourceRef.value.disconnect()
      } catch {
        /* ignore */
      }
      mediaSourceRef.value = null
    }
    if (micStreamRef.value) {
      micStreamRef.value.getTracks().forEach((track) => track.stop())
      micStreamRef.value = null
    }
    const ctx = audioContextRef.value
    if (ctx && ctx.state !== 'closed') {
      void ctx.close().catch(() => {})
    }
    audioContextRef.value = null
    unregisterVisibilityListener()
  }

  function closeSocket(sendStop: boolean): void {
    const sock = wsRef.value
    wsRef.value = null
    if (!sock) return
    intentionalClose = true
    try {
      if (sendStop && sock.readyState === WebSocket.OPEN) {
        sock.send(JSON.stringify({ type: 'stop' }))
      }
    } catch {
      /* ignore */
    }
    try {
      sock.close()
    } catch {
      /* ignore */
    }
  }

  function appendFinalLine(text: string): void {
    const line = text.trim()
    if (!line) return
    const next = [...lines.value, line]
    lines.value = next.length > MAX_COMMITTED_LINES ? next.slice(-MAX_COMMITTED_LINES) : next
    liveText.value = ''
  }

  function handleServerPayload(data: Record<string, unknown>, sessionStamp: number): void {
    if (sessionStamp !== currentSessionStamp) return
    const typ = String(data.type ?? '')
    if (typ === 'started') {
      connecting.value = false
      sessionReady.value = true
      clearStartedTimeout()
      return
    }
    if (typ === 'partial') {
      liveText.value = String(data.text ?? '')
      if (liveText.value.trim()) markSpeechActivity()
      return
    }
    if (typ === 'final') {
      appendFinalLine(String(data.text ?? ''))
      markSpeechActivity()
      return
    }
    if (typ === 'stopped') {
      connecting.value = false
      sessionReady.value = false
      return
    }
    if (typ === 'error') {
      const code = String(data.code ?? '')
      const msg = String(data.message ?? t('auth.voiceNotes.genericError'))
      error.value = msg
      if (code === 'daily_token_cap' || code === 'thinking_coin' || code === 'budget') {
        notify.warning(msg || t('auth.voiceNotes.budgetExceeded'))
        void stopRecording('upstream_error')
        return
      }
      if (code === 'connection_limit') {
        notify.warning(t('auth.voiceNotes.sessionBusy'))
        void abortSession('ws_error')
        return
      }
      notify.warning(msg)
      if (code === 'asr_config' || code === 'upstream' || code === 'relay') {
        void stopRecording('upstream_error')
      }
    }
  }

  function micConflictActive(): boolean {
    const kitty = useKittySessionStore()
    const liveTranslation = useLiveTranslationStore()
    const liveSubtitles = useLiveSubtitlesStore()
    return (
      kitty.asrListening ||
      liveTranslation.enabled ||
      liveTranslation.connecting ||
      liveSubtitles.enabled ||
      liveSubtitles.connecting
    )
  }

  async function startMicrophoneAndAttach(sessionStamp: number): Promise<void> {
    const AudioCtx =
      window.AudioContext ||
      (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AudioCtx) {
      throw new Error('AudioContext not supported')
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        sampleRate: VOICE_NOTES_TARGET_SAMPLE_RATE,
      },
    })

    if (sessionStamp !== currentSessionStamp || !recording.value) {
      stream.getTracks().forEach((track) => track.stop())
      return
    }

    const ctx = new AudioCtx()
    audioContextRef.value = ctx
    micStreamRef.value = stream
    registerTrackEndedListener(stream)

    if (ctx.state === 'suspended') {
      await ctx.resume()
    }

    if (sessionStamp !== currentSessionStamp || !recording.value || ctx.state === 'closed') {
      stream.getTracks().forEach((track) => track.stop())
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
      if (paused.value || stopping.value) return
      const inputData = event.inputBuffer.getChannelData(0)
      const rms = float32Rms(inputData)
      publishInputLevel(rms)
      if (rms >= VOICE_NOTES_SPEECH_RMS_THRESHOLD) {
        markSpeechActivity()
      }
      const sock = wsRef.value
      if (!sock || sock.readyState !== WebSocket.OPEN || !sessionReady.value) return
      const audioB64 = float32ToPcm16Base64(inputData, ctx.sampleRate)
      try {
        sock.send(JSON.stringify({ type: 'append', audio: audioB64 }))
      } catch {
        /* ignore */
      }
    }

    source.connect(processor)
    processor.connect(ctx.destination)
    registerVisibilityListener()
  }

  async function ensureDocSummaryPackage(savedId: string, title: string): Promise<number> {
    const pkg = await apiRequestJson<DocSummaryPackage>(`${DOC_SUMMARY_API_BASE}/session/start`, {
      method: 'POST',
      body: JSON.stringify({
        diagram_id: savedId,
        diagram_title: title,
        create_if_missing: true,
      }),
    })
    return pkg.id
  }

  async function enableAndOpen(): Promise<void> {
    if (!authStore.isAuthenticated) {
      notify.warning(t('auth.voiceNotes.loginRequired'))
      return
    }
    enabled.value = true
    modalOpen.value = false
    error.value = null
    registerPageHideListener()
  }

  async function abortSession(reason: VoiceNotesStopReason): Promise<void> {
    clearStartedTimeout()
    clearWatchTimers()
    resetInputLevel()
    connecting.value = false
    sessionReady.value = false
    recording.value = false
    paused.value = false
    stopMicrophoneGraph()
    closeSocket(false)
    lastStopReason.value = reason
    currentSessionStamp += 1
  }

  async function startRecording(): Promise<void> {
    if (!enabled.value || connecting.value || recording.value || stopping.value) return
    if (!navigator.mediaDevices?.getUserMedia) {
      notify.warning(t('auth.voiceNotes.micUnavailable'))
      return
    }
    if (micConflictActive()) {
      notify.warning(t('auth.voiceNotes.micConflict'))
      return
    }

    connecting.value = true
    recording.value = true
    paused.value = false
    sessionReady.value = false
    error.value = null
    lastStopReason.value = null
    intentionalClose = false
    const sessionStamp = ++currentSessionStamp
    const socket = new WebSocket(buildVoiceNotesWebSocketUrl())
    wsRef.value = socket
    armStartedTimeout(sessionStamp)

    socket.onopen = () => {
      try {
        socket.send(
          JSON.stringify({
            type: 'start',
            language_hints: mapPromptLanguageToHints(String(uiStore.promptLanguage)),
          })
        )
      } catch {
        notify.warning(t('auth.voiceNotes.wsError'))
        void abortSession('ws_error')
        return
      }

      startSessionWatchers()
      void startMicrophoneAndAttach(sessionStamp).catch(() => {
        notify.warning(t('auth.voiceNotes.micFailed'))
        void abortSession('mic_lost')
      })
    }

    socket.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string) as Record<string, unknown>
        handleServerPayload(data, sessionStamp)
      } catch {
        /* ignore */
      }
    }

    socket.onerror = () => {
      if (sessionStamp !== currentSessionStamp) return
      if (connecting.value || !sessionReady.value) {
        notify.warning(t('auth.voiceNotes.wsError'))
      }
    }

    socket.onclose = (event: CloseEvent) => {
      if (sessionStamp !== currentSessionStamp) return
      wsRef.value = null
      const wasIntentional = intentionalClose
      intentionalClose = false
      if (wasIntentional || stopping.value) {
        connecting.value = false
        return
      }
      if (event.code === 4001) {
        notify.warning(t('auth.voiceNotes.authFailed'))
        void stopRecording('auth')
        return
      }
      if (recording.value || paused.value) {
        notify.warning(t('auth.voiceNotes.wsClosed'))
        void stopRecording('ws_closed')
        return
      }
      connecting.value = false
      sessionReady.value = false
      stopMicrophoneGraph()
      clearWatchTimers()
    }
  }

  function pauseRecording(): void {
    if (!recording.value || paused.value || stopping.value) return
    pausedAccumulatedMs = elapsedMs.value
    paused.value = true
    resetInputLevel()
    // Freeze silence clock while paused — intentional quiet time.
    markSpeechActivity()
  }

  function resumeRecording(): void {
    if (!recording.value || !paused.value || stopping.value) return
    recordingStartedAt = Date.now()
    paused.value = false
    markSpeechActivity()
    const ctx = audioContextRef.value
    if (ctx && ctx.state === 'suspended') {
      void ctx.resume().catch(() => {})
    }
  }

  async function ingestTranscript(): Promise<void> {
    const text = transcriptText.value.trim()
    if (!text) return

    const ok = await ensureMindmapSession()
    if (!ok) return

    const pkgId = packageId.value
    if (!pkgId) return

    const clipped =
      text.length > DOC_SUMMARY_MAX_INPUT_CHARS ? text.slice(0, DOC_SUMMARY_MAX_INPUT_CHARS) : text
    ingesting.value = true
    try {
      const lang = String(uiStore.promptLanguage || 'zh').split('-')[0] || 'zh'
      await apiRequestJson(`${DOC_SUMMARY_PACKAGES_BASE}/${pkgId}/documents/ingest-text`, {
        method: 'POST',
        body: JSON.stringify({
          content: clipped,
          title: formatVoiceNoteTitle(),
          language: lang,
        }),
      })
      tryOpenDocSummaryPanel()
    } catch (exc) {
      const msg = exc instanceof Error ? exc.message : t('auth.voiceNotes.ingestFailed')
      error.value = msg
      notify.warning(msg)
    } finally {
      ingesting.value = false
    }
  }

  function tryOpenDocSummaryPanel(): void {
    const id = diagramId.value
    if (!id) return
    const route = router.currentRoute.value
    const routeDiagramId = typeof route.query.diagramId === 'string' ? route.query.diagramId : null
    if (route.path !== '/canvas' || routeDiagramId !== id) return
    try {
      useMindMapSideToolbarState().openTool('document_summary')
    } catch {
      /* canvas toolbar may not be mounted yet */
    }
  }

  async function stopRecording(reason: VoiceNotesStopReason = 'user'): Promise<void> {
    if (stopping.value) return
    if (!recording.value && !paused.value) return
    stopping.value = true
    lastStopReason.value = reason
    paused.value = false
    recording.value = false
    sessionReady.value = false
    resetInputLevel()
    clearWatchTimers()
    clearStartedTimeout()
    stopMicrophoneGraph()

    if (liveText.value.trim()) {
      appendFinalLine(liveText.value)
    }

    const sock = wsRef.value
    if (sock && sock.readyState === WebSocket.OPEN) {
      intentionalClose = true
      try {
        sock.send(JSON.stringify({ type: 'stop' }))
      } catch {
        /* ignore */
      }
      await sleep(400)
    }
    closeSocket(false)
    connecting.value = false
    try {
      if (reason !== 'pagehide') {
        await ingestTranscript()
      }
    } finally {
      stopping.value = false
    }
  }

  async function exit(): Promise<void> {
    if (recording.value || paused.value) {
      await stopRecording('exit')
    } else {
      clearWatchTimers()
      clearStartedTimeout()
      stopMicrophoneGraph()
      closeSocket(false)
    }
    unregisterPageHideListener()
    enabled.value = false
    modalOpen.value = false
    connecting.value = false
    paused.value = false
    recording.value = false
    sessionReady.value = false
    stopping.value = false
    packageId.value = null
    diagramId.value = null
    lines.value = []
    liveText.value = ''
    elapsedMs.value = 0
    error.value = null
    resetInputLevel()
    currentSessionStamp += 1
  }

  watch(
    () => authStore.isAuthenticated,
    (isAuth, wasAuth) => {
      if (wasAuth && !isAuth && enabled.value) {
        void exit()
      }
    }
  )

  return {
    enabled,
    bootstrapping,
    modalOpen,
    recording,
    paused,
    connecting,
    ingesting,
    stopping,
    sessionReady,
    sessionStatus,
    inputLevel,
    lines,
    liveText,
    elapsedMs,
    packageId,
    diagramId,
    error,
    lastStopReason,
    transcriptText,
    hasActiveCapture,
    enableAndOpen,
    openModal,
    closeModal,
    jumpToMindmap,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
    exit,
  }
})
