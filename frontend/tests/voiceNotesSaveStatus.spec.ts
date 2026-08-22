import { describe, expect, it } from 'vitest'

import {
  resolveVoiceNotesSaveLabelKind,
  voiceNotesSavedAge,
  voiceNotesSavedAgeMessage,
} from '@/composables/voiceNotes/voiceNotesSaveStatus'

describe('resolveVoiceNotesSaveLabelKind', () => {
  it('keeps live session lines and overlays save state after ingest', () => {
    expect(
      resolveVoiceNotesSaveLabelKind({
        statusLine: 'recordingAndSeparating',
        isDirty: false,
        lastSavedAt: null,
      })
    ).toBe('session')
    expect(
      resolveVoiceNotesSaveLabelKind({
        statusLine: 'savingTranscript',
        isDirty: true,
        lastSavedAt: 1,
      })
    ).toBe('saving')
    expect(
      resolveVoiceNotesSaveLabelKind({
        statusLine: 'ready',
        isDirty: true,
        lastSavedAt: 1,
      })
    ).toBe('unsaved')
    expect(
      resolveVoiceNotesSaveLabelKind({
        statusLine: 'ready',
        isDirty: false,
        lastSavedAt: null,
      })
    ).toBe('unsaved')
    expect(
      resolveVoiceNotesSaveLabelKind({
        statusLine: 'ready',
        isDirty: false,
        lastSavedAt: 1,
      })
    ).toBe('saved')
  })
})

describe('voiceNotesSavedAge', () => {
  const savedAt = 1_000_000

  it('matches the canvas relative buckets', () => {
    expect(voiceNotesSavedAge(savedAt, savedAt + 9_000)).toEqual({ unit: 'justNow' })
    expect(voiceNotesSavedAge(savedAt, savedAt + 12_000)).toEqual({ unit: 'seconds', n: 12 })
    expect(voiceNotesSavedAge(savedAt, savedAt + 120_000)).toEqual({ unit: 'minutes', n: 2 })
    expect(voiceNotesSavedAge(savedAt, savedAt + 3_600_000)).toEqual({ unit: 'clock' })
  })

  it('maps buckets to transcript save copy', () => {
    expect(voiceNotesSavedAgeMessage({ unit: 'justNow' }, '12:00')).toEqual({
      key: 'auth.voiceNotes.savedJustNow',
    })
    expect(voiceNotesSavedAgeMessage({ unit: 'seconds', n: 12 }, '12:00')).toEqual({
      key: 'auth.voiceNotes.savedSecondsAgo',
      named: { n: 12 },
    })
    expect(voiceNotesSavedAgeMessage({ unit: 'minutes', n: 3 }, '12:00')).toEqual({
      key: 'auth.voiceNotes.savedMinutesAgo',
      named: { n: 3 },
    })
    expect(voiceNotesSavedAgeMessage({ unit: 'clock' }, '14:05')).toEqual({
      key: 'auth.voiceNotes.savedAt',
      named: { time: '14:05' },
    })
  })
})
