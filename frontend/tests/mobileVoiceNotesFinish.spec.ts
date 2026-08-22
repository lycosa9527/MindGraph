import { describe, expect, it } from 'vitest'

import {
  formatVoiceNoteHistoryTitle,
  isMobileAppPath,
  resolveVoiceNotesActions,
  resolveVoiceNotesCanvasPath,
  resolveVoiceNotesStatusLine,
  shouldGenerateMindmapAfterVoiceStop,
  shouldWarnEmptyVoiceTranscript,
  voiceNotesHistoryListUrl,
  voiceNotesStatusMessageKey,
} from '@/composables/voiceNotes/mobileVoiceNotesFinish'

describe('shouldGenerateMindmapAfterVoiceStop', () => {
  const ready = {
    lastStopReason: 'user' as const,
    transcript: 'hello from a meeting',
    packageId: 12,
    diagramId: 'diag-1',
  }

  it('generates when transcript was ingested into a linked package', () => {
    expect(shouldGenerateMindmapAfterVoiceStop(ready)).toBe(true)
    expect(shouldGenerateMindmapAfterVoiceStop({ ...ready, lastStopReason: 'silence' })).toBe(true)
  })

  it('skips page hide, exit, empty transcript, and missing session ids', () => {
    expect(shouldGenerateMindmapAfterVoiceStop({ ...ready, lastStopReason: 'pagehide' })).toBe(
      false
    )
    expect(shouldGenerateMindmapAfterVoiceStop({ ...ready, lastStopReason: 'exit' })).toBe(false)
    expect(shouldGenerateMindmapAfterVoiceStop({ ...ready, transcript: '   ' })).toBe(false)
    expect(shouldGenerateMindmapAfterVoiceStop({ ...ready, packageId: null })).toBe(false)
    expect(shouldGenerateMindmapAfterVoiceStop({ ...ready, diagramId: null })).toBe(false)
  })
})

describe('shouldWarnEmptyVoiceTranscript', () => {
  it('warns only after a user stop with no speech (silence already has its own toast)', () => {
    expect(shouldWarnEmptyVoiceTranscript({ lastStopReason: 'user', transcript: '' })).toBe(true)
    expect(shouldWarnEmptyVoiceTranscript({ lastStopReason: 'silence', transcript: '  ' })).toBe(
      false
    )
    expect(shouldWarnEmptyVoiceTranscript({ lastStopReason: 'ws_error', transcript: '' })).toBe(
      false
    )
    expect(shouldWarnEmptyVoiceTranscript({ lastStopReason: 'user', transcript: 'hi' })).toBe(false)
  })
})

describe('resolveVoiceNotesCanvasPath', () => {
  it('keeps mobile users on the mobile canvas', () => {
    expect(isMobileAppPath('/m')).toBe(true)
    expect(isMobileAppPath('/m/mindgraph')).toBe(true)
    expect(isMobileAppPath('/m/voice-notes')).toBe(true)
    expect(isMobileAppPath('/mindgraph')).toBe(false)
    expect(isMobileAppPath('/mindmate')).toBe(false)
    expect(resolveVoiceNotesCanvasPath('/m/mindgraph')).toBe('/m/canvas')
    expect(resolveVoiceNotesCanvasPath('/m')).toBe('/m/canvas')
    expect(resolveVoiceNotesCanvasPath('/canvas')).toBe('/canvas')
    expect(resolveVoiceNotesCanvasPath('/mindgraph')).toBe('/canvas')
  })
})

describe('formatVoiceNoteHistoryTitle', () => {
  it('formats the default stamp title and leaves other titles alone', () => {
    expect(formatVoiceNoteHistoryTitle('voice recording_202608230012')).toBe('2026-08-23 00:12')
    expect(formatVoiceNoteHistoryTitle('circle map')).toBe('circle map')
  })
})

describe('resolveVoiceNotesStatusLine', () => {
  const idle = {
    generating: false,
    persisting: false,
    sessionStatus: 'idle',
    hasTranscript: false,
  }

  it('covers waiting, ASR, recording with talkers, and ready', () => {
    expect(resolveVoiceNotesStatusLine(idle)).toBe('waiting')
    expect(resolveVoiceNotesStatusLine({ ...idle, sessionStatus: 'connecting' })).toBe(
      'connectingAsr'
    )
    expect(resolveVoiceNotesStatusLine({ ...idle, sessionStatus: 'starting' })).toBe(
      'connectingAsr'
    )
    expect(resolveVoiceNotesStatusLine({ ...idle, sessionStatus: 'recording' })).toBe(
      'recordingAndSeparating'
    )
    expect(resolveVoiceNotesStatusLine({ ...idle, sessionStatus: 'paused' })).toBe('paused')
    expect(resolveVoiceNotesStatusLine({ ...idle, sessionStatus: 'stopping' })).toBe('stopping')
    expect(resolveVoiceNotesStatusLine({ ...idle, sessionStatus: 'ingesting' })).toBe(
      'savingTranscript'
    )
    expect(resolveVoiceNotesStatusLine({ ...idle, generating: true })).toBe('generating')
    expect(resolveVoiceNotesStatusLine({ ...idle, hasTranscript: true })).toBe('ready')
    expect(voiceNotesStatusMessageKey('waiting')).toBe('auth.voiceNotes.status.waiting')
  })
})

describe('resolveVoiceNotesActions', () => {
  const idle = {
    recording: false,
    paused: false,
    connecting: false,
    sessionReady: false,
    stopping: false,
    ingesting: false,
    bootstrapping: false,
    hasTranscript: false,
    hasActiveCapture: false,
  }

  it('locks pause until ASR is ready and blocks start while ingesting', () => {
    const handshake = resolveVoiceNotesActions({
      ...idle,
      recording: true,
      connecting: true,
      hasActiveCapture: true,
    })
    expect(handshake.canStart).toBe(false)
    expect(handshake.canPause).toBe(false)
    expect(handshake.canStop).toBe(true)

    const live = resolveVoiceNotesActions({
      ...idle,
      recording: true,
      sessionReady: true,
      hasActiveCapture: true,
      hasTranscript: true,
    })
    expect(live.canPause).toBe(true)
    expect(live.canStop).toBe(true)
    expect(live.canCopy).toBe(true)

    const saving = resolveVoiceNotesActions({ ...idle, ingesting: true, hasTranscript: true })
    expect(saving.canStart).toBe(false)
    expect(saving.canJump).toBe(false)
    expect(saving.canGenerate).toBe(false)
  })
})

describe('voiceNotesHistoryListUrl', () => {
  it('asks the library API for the voice_notes channel', () => {
    expect(voiceNotesHistoryListUrl(1, 50)).toBe(
      '/api/diagrams?page=1&page_size=50&source_channel=voice_notes'
    )
    expect(voiceNotesHistoryListUrl(2, 20)).toBe(
      '/api/diagrams?page=2&page_size=20&source_channel=voice_notes'
    )
  })
})
