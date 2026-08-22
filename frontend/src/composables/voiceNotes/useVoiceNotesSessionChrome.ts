/**
 * Shared Voice Notes status line + button flags for modal, FAB, and mobile.
 * After ingest, the header uses a canvas-style "transcript saved … ago" label
 * bound to this session's markdown document.
 */
import { type Ref, computed, onMounted, onUnmounted, ref } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import {
  resolveVoiceNotesActions,
  resolveVoiceNotesStatusLine,
  voiceNotesStatusMessageKey,
} from '@/composables/voiceNotes/mobileVoiceNotesFinish'
import {
  resolveVoiceNotesSaveLabelKind,
  voiceNotesSavedAge,
  voiceNotesSavedAgeMessage,
} from '@/composables/voiceNotes/voiceNotesSaveStatus'
import type { LocaleCode } from '@/i18n/locales'
import { intlLocaleForUiCode } from '@/i18n/locales'
import { useVoiceNotesStore } from '@/stores/voiceNotes'

export function useVoiceNotesSessionChrome(extra?: {
  generating?: Ref<boolean>
  persisting?: Ref<boolean>
}) {
  const { t, currentLanguage } = useLanguage()
  const voiceNotes = useVoiceNotesStore()
  const nowMs = ref(Date.now())
  let relativeTimer: ReturnType<typeof setInterval> | null = null

  const statusLine = computed(() =>
    resolveVoiceNotesStatusLine({
      generating: extra?.generating?.value ?? false,
      persisting: extra?.persisting?.value ?? false,
      sessionStatus: voiceNotes.sessionStatus,
      hasTranscript: voiceNotes.transcriptText.trim().length > 0,
    })
  )

  const saveKind = computed(() =>
    resolveVoiceNotesSaveLabelKind({
      statusLine: statusLine.value,
      isDirty: voiceNotes.transcriptDirty,
      lastSavedAt: voiceNotes.lastSavedAt,
    })
  )

  const sessionLabel = computed(() => t(voiceNotesStatusMessageKey(statusLine.value)))

  const statusLabel = computed(() => {
    const kind = saveKind.value
    if (kind === 'session') {
      return t(voiceNotesStatusMessageKey(statusLine.value))
    }
    if (kind === 'saving') {
      return t('auth.voiceNotes.status.savingTranscript')
    }
    if (kind === 'unsaved') {
      return t('auth.voiceNotes.unsavedChanges')
    }
    const savedAt = voiceNotes.lastSavedAt
    if (savedAt == null) {
      return t(voiceNotesStatusMessageKey('ready'))
    }
    const age = voiceNotesSavedAge(savedAt, nowMs.value)
    const clockLabel = new Date(savedAt).toLocaleTimeString(
      intlLocaleForUiCode(currentLanguage.value as LocaleCode),
      { hour: '2-digit', minute: '2-digit', hour12: false }
    )
    const message = voiceNotesSavedAgeMessage(age, clockLabel)
    return message.named ? t(message.key, message.named) : t(message.key)
  })

  const statusClickable = computed(() => saveKind.value === 'unsaved')

  function onStatusClick(): void {
    if (!statusClickable.value) return
    void voiceNotes.flushTranscriptIfEdited()
  }

  const actions = computed(() =>
    resolveVoiceNotesActions({
      recording: voiceNotes.recording,
      paused: voiceNotes.paused,
      connecting: voiceNotes.connecting,
      sessionReady: voiceNotes.sessionReady,
      stopping: voiceNotes.stopping,
      ingesting: voiceNotes.ingesting,
      bootstrapping: voiceNotes.bootstrapping,
      generating: extra?.generating?.value,
      persisting: extra?.persisting?.value,
      hasTranscript: voiceNotes.transcriptText.trim().length > 0,
      hasActiveCapture: voiceNotes.hasActiveCapture,
    })
  )

  onMounted(() => {
    relativeTimer = setInterval(() => {
      nowMs.value = Date.now()
    }, 1000)
  })

  onUnmounted(() => {
    if (relativeTimer !== null) {
      clearInterval(relativeTimer)
      relativeTimer = null
    }
  })

  return {
    statusLine,
    sessionLabel,
    statusLabel,
    saveKind,
    statusClickable,
    onStatusClick,
    actions,
  }
}
