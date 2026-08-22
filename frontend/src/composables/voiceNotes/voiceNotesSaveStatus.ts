/**
 * Canvas-style relative save label for the Voice Notes header.
 * The timestamp is the session markdown (doc-summary ingest), not the mindmap.
 */
import type { VoiceNotesStatusLine } from '@/composables/voiceNotes/mobileVoiceNotesFinish'

export type VoiceNotesSaveLabelKind = 'session' | 'saving' | 'unsaved' | 'saved'

export type VoiceNotesSavedAge =
  | { unit: 'justNow' }
  | { unit: 'seconds'; n: number }
  | { unit: 'minutes'; n: number }
  | { unit: 'clock' }

export function resolveVoiceNotesSaveLabelKind(input: {
  statusLine: VoiceNotesStatusLine
  isDirty: boolean
  lastSavedAt: number | null
}): VoiceNotesSaveLabelKind {
  if (input.statusLine === 'savingTranscript') return 'saving'
  if (input.statusLine !== 'ready') return 'session'
  if (input.isDirty || input.lastSavedAt == null) return 'unsaved'
  return 'saved'
}

export function voiceNotesSavedAge(savedAtMs: number, nowMs: number): VoiceNotesSavedAge {
  const diffSec = Math.max(0, Math.floor((nowMs - savedAtMs) / 1000))
  if (diffSec < 10) return { unit: 'justNow' }
  if (diffSec < 60) return { unit: 'seconds', n: diffSec }
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return { unit: 'minutes', n: diffMin }
  return { unit: 'clock' }
}

export function voiceNotesSavedAgeMessage(
  age: VoiceNotesSavedAge,
  clockLabel: string
): { key: string; named?: Record<string, unknown> } {
  if (age.unit === 'justNow') {
    return { key: 'auth.voiceNotes.savedJustNow' }
  }
  if (age.unit === 'seconds') {
    return { key: 'auth.voiceNotes.savedSecondsAgo', named: { n: age.n } }
  }
  if (age.unit === 'minutes') {
    return { key: 'auth.voiceNotes.savedMinutesAgo', named: { n: age.n } }
  }
  return { key: 'auth.voiceNotes.savedAt', named: { time: clockLabel } }
}
