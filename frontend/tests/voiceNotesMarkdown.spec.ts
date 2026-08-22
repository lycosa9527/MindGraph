import { describe, expect, it } from 'vitest'

import {
  parseVoiceNotesMarkdown,
  serializeVoiceNotesMarkdown,
  voiceNotesMarkdownBody,
} from '@/utils/voiceNotesMarkdown'
import type { VoiceNotesTurn } from '@/utils/voiceNotesTranscript'
import { parseVoiceNotesTranscript } from '@/utils/voiceNotesTranscript'

function turn(speakerId: number, text: string, sentenceId: number): VoiceNotesTurn {
  return { speakerId, text, live: false, sentenceId, startTime: sentenceId * 10 }
}

describe('voice notes markdown interchange', () => {
  it('round-trips talker names, remaps, and voiceprint id', () => {
    const markdown = serializeVoiceNotesMarkdown({
      turns: [turn(0, '你好', 0), turn(2, '在的', 1)],
      speakerNames: { 2: 'Roy' },
      speakerIds: [0, 1, 2],
      speakerRemaps: { 3: 0 },
      speakerContextId: 'vp_abc-1',
      savedAt: 1_700_000_128_000,
      elapsedMs: 28_000,
      labelForSpeakerId: (id) => (id === 2 ? 'Roy：' : `说话人${id + 1}：`),
    })
    expect(markdown.startsWith('说话人1：你好\nRoy：在的')).toBe(true)
    expect(markdown).toContain('mg-voice-notes:1')
    expect(voiceNotesMarkdownBody(markdown)).toBe('说话人1：你好\nRoy：在的')

    const restored = parseVoiceNotesMarkdown(markdown)
    expect(restored.turns.map((item) => [item.speakerId, item.text])).toEqual([
      [0, '你好'],
      [2, '在的'],
    ])
    expect(restored.speakerNames).toEqual({ 2: 'Roy' })
    expect(restored.speakerIds).toEqual([0, 1, 2])
    expect(restored.speakerRemaps).toEqual({ 3: 0 })
    expect(restored.speakerContextId).toBe('vp_abc-1')
    expect(restored.savedAt).toBe(1_700_000_128_000)
    expect(restored.elapsedMs).toBe(28_000)
  })

  it('keeps legacy speaker-prefixed markdown without a meta comment', () => {
    const restored = parseVoiceNotesMarkdown('Roy：你好\n说话人2：在吗')
    expect(restored.turns.map((item) => [item.speakerId, item.text])).toEqual([
      [0, '你好'],
      [1, '在吗'],
    ])
    expect(restored.speakerNames).toEqual({ 0: 'Roy' })
    expect(restored.speakerContextId).toBe('')
    expect(restored.savedAt).toBeNull()
  })

  it('does not treat the meta fence as transcript lines', () => {
    const parsed = parseVoiceNotesTranscript(
      ['说话人1：你好', '<!-- mg-voice-notes:1', '{"v":1}', '-->'].join('\n')
    )
    expect(parsed.turns.map((item) => item.text)).toEqual(['你好'])
  })
})
