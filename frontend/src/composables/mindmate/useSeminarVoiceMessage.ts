/**
 * Short voice clip for one seminar message. Face-to-face notes stay on the voice-notes modal.
 */
import { onUnmounted, ref } from 'vue'

import { useNotifications } from '@/composables/core/useNotifications'
import { useVoiceNotesStore } from '@/stores/voiceNotes'

const MIN_MS = 500

function recorderMime(): { mime: string; extension: string } | null {
  if (typeof MediaRecorder === 'undefined') {
    return null
  }
  const options: Array<{ mime: string; extension: string }> = [
    { mime: 'audio/webm;codecs=opus', extension: 'webm' },
    { mime: 'audio/webm', extension: 'webm' },
    { mime: 'audio/mp4', extension: 'm4a' },
  ]
  const match = options.find((option) => MediaRecorder.isTypeSupported(option.mime))
  return match ?? null
}

export function useSeminarVoiceMessage() {
  const notify = useNotifications()
  const voiceNotes = useVoiceNotesStore()
  const recording = ref(false)
  const elapsedLabel = ref('0:00')

  let recorder: MediaRecorder | null = null
  let stream: MediaStream | null = null
  let chunks: Blob[] = []
  let startedAt = 0
  let timer = 0
  let mime = ''
  let extension = 'webm'
  let stopWait: ((file: File | null) => void) | null = null
  let queuedRelease: 'send' | 'cancel' | null = null

  function tick(): void {
    const seconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
    const mm = String(Math.floor(seconds / 60))
    const ss = String(seconds % 60).padStart(2, '0')
    elapsedLabel.value = `${mm}:${ss}`
  }

  function releaseStream(): void {
    stream?.getTracks().forEach((track) => track.stop())
    stream = null
  }

  function resetClock(): void {
    window.clearInterval(timer)
    timer = 0
    elapsedLabel.value = '0:00'
    startedAt = 0
  }

  function noteRelease(send: boolean): void {
    queuedRelease = send ? 'send' : 'cancel'
  }

  async function start(): Promise<File | null | 'holding' | 'aborted'> {
    if (recording.value) {
      return 'holding'
    }
    queuedRelease = null
    if (voiceNotes.recording || voiceNotes.connecting) {
      notify.warningKey('auth.voiceNotes.micConflict')
      return 'aborted'
    }
    const picked = recorderMime()
    if (!picked || !navigator.mediaDevices?.getUserMedia) {
      notify.warningKey('auth.voiceNotes.micUnavailable')
      return 'aborted'
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      notify.warningKey('auth.voiceNotes.micFailed')
      return 'aborted'
    }
    if (queuedRelease === 'cancel') {
      releaseStream()
      queuedRelease = null
      return 'aborted'
    }
    mime = picked.mime
    extension = picked.extension
    chunks = []
    recorder = new MediaRecorder(stream, { mimeType: mime })
    recorder.addEventListener('dataavailable', (event) => {
      if (event.data.size > 0) {
        chunks.push(event.data)
      }
    })
    recorder.addEventListener('stop', () => {
      const waited = stopWait
      stopWait = null
      releaseStream()
      recording.value = false
      const tooShort = Date.now() - startedAt < MIN_MS
      resetClock()
      if (!waited) {
        chunks = []
        return
      }
      if (tooShort || chunks.length === 0) {
        chunks = []
        waited(null)
        return
      }
      const blob = new Blob(chunks, { type: mime })
      chunks = []
      const file = new File([blob], `voice-${Date.now()}.${extension}`, { type: mime })
      waited(file)
    })
    startedAt = Date.now()
    recording.value = true
    tick()
    timer = window.setInterval(tick, 250)
    try {
      recorder.start()
    } catch {
      cancel()
      notify.warningKey('mindmate.composer.voiceFailed')
      return 'aborted'
    }
    const queued = queuedRelease
    queuedRelease = null
    if (queued === 'cancel') {
      cancel()
      return 'aborted'
    }
    if (queued === 'send') {
      return stop()
    }
    return 'holding'
  }

  function stop(): Promise<File | null> {
    if (!recorder || recorder.state === 'inactive') {
      recording.value = false
      resetClock()
      return Promise.resolve(null)
    }
    return new Promise((resolve) => {
      stopWait = resolve
      recorder?.stop()
    })
  }

  function cancel(): void {
    stopWait = null
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
      return
    }
    releaseStream()
    recording.value = false
    resetClock()
    chunks = []
  }

  onUnmounted(() => {
    cancel()
  })

  return { recording, elapsedLabel, start, stop, cancel, noteRelease }
}
