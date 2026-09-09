import { describe, expect, it } from 'vitest'

import {
  isCanvasVoiceNotesPath,
  VOICE_NOTES_INGEST_SOURCE,
  VOICE_NOTES_LIVE_SAVE_MS,
} from '@/composables/voiceNotes/mobileVoiceNotesFinish'
import {
  resolveCanvasDiagramId,
  shouldBlockDiagramRebind,
  shouldReuseBoundVoiceNotes,
  voiceNotesMarkdownUrl,
} from '@/composables/voiceNotes/voiceNotesBind'

describe('voiceNotesBind', () => {
  it('prefers the route diagram id over the active library id', () => {
    expect(
      resolveCanvasDiagramId({
        routeDiagramId: ' route-1 ',
        activeDiagramId: 'active-2',
      })
    ).toBe('route-1')
    expect(
      resolveCanvasDiagramId({
        routeDiagramId: null,
        activeDiagramId: ' active-2 ',
      })
    ).toBe('active-2')
    expect(resolveCanvasDiagramId({ routeDiagramId: '', activeDiagramId: null })).toBe(null)
  })

  it('reuses an in-memory transcript and blocks switching while recording', () => {
    expect(
      shouldReuseBoundVoiceNotes({
        boundDiagramId: 'd1',
        targetDiagramId: 'd1',
        hasActiveCapture: false,
        hasLocalTurns: true,
      })
    ).toBe(true)
    expect(
      shouldBlockDiagramRebind({
        boundDiagramId: 'd1',
        targetDiagramId: 'd2',
        hasActiveCapture: true,
      })
    ).toBe(true)
    expect(
      shouldBlockDiagramRebind({
        boundDiagramId: 'd1',
        targetDiagramId: 'd2',
        hasActiveCapture: false,
      })
    ).toBe(false)
  })

  it('asks COS for the voice-notes markdown source on canvas paths', () => {
    expect(isCanvasVoiceNotesPath('/canvas')).toBe(true)
    expect(isCanvasVoiceNotesPath('/m/canvas')).toBe(true)
    expect(isCanvasVoiceNotesPath('/m/voice-notes')).toBe(false)
    expect(voiceNotesMarkdownUrl(9, VOICE_NOTES_INGEST_SOURCE)).toBe(
      '/api/doc-summary/9/md?ingest_source=voice_notes'
    )
    expect(VOICE_NOTES_LIVE_SAVE_MS).toBe(30_000)
  })
})
