import { describe, expect, it } from 'vitest'

import {
  applySpeakerRemaps,
  coalesceConsecutiveSpeakerTurns,
  collectSnapshotSpeakerIds,
  commitLiveTurns,
  defaultSpeakerSlot,
  fitVoiceNotesTextarea,
  formatVoiceNotesSpeakerLine,
  joinVoiceNotesSentences,
  linesFromEditedTranscript,
  mergeCaptureSnapshotTurns,
  mergeSpeakerSlots,
  parseVoiceNotesTranscript,
  relabelTranscriptLines,
  remainingVoiceNotesDurationMs,
  remapTurnSpeakerIds,
  resolveCustomSpeakerLabel,
  shouldStopVoiceNotesOnServerError,
  speakerAvatarGlyph,
  speakerDisplayName,
  speakerIdsAfterRemoving,
  speakerIdsWithRemaps,
  speakerLabelSuffix,
  splitVoiceNotesSnapshot,
  transcriptFromTurns,
  turnsFromSnapshot,
  voiceNotesErrorI18nKey,
} from '@/utils/voiceNotesTranscript'

describe('fitVoiceNotesTextarea', () => {
  it('grows the editor to the wrapped scroll height', () => {
    const el = {
      scrollHeight: 96,
      style: { height: '' },
    } as HTMLTextAreaElement
    fitVoiceNotesTextarea(el)
    expect(el.style.height).toBe('96px')
  })
})

describe('formatVoiceNotesSpeakerLine', () => {
  it('prefixes a known speaker and leaves unknown ids alone', () => {
    expect(formatVoiceNotesSpeakerLine('  你好  ', 0, '说话人1：')).toBe('说话人1：你好')
    expect(formatVoiceNotesSpeakerLine('你好', -1, '说话人1：')).toBe('你好')
    expect(formatVoiceNotesSpeakerLine('你好', 0, '')).toBe('你好')
  })
})

describe('speaker name labels', () => {
  it('resolves custom names and relabels transcript prefixes', () => {
    expect(speakerLabelSuffix('说话人{n}：')).toBe('：')
    expect(speakerLabelSuffix('Speaker {n}: ')).toBe(': ')
    expect(resolveCustomSpeakerLabel('', '说话人1：', '：')).toBe('说话人1：')
    expect(resolveCustomSpeakerLabel('张三', '说话人1：', '：')).toBe('张三：')
    expect(resolveCustomSpeakerLabel('张三：', '说话人1：', '：')).toBe('张三：')
    expect(
      relabelTranscriptLines(['说话人1：你好', '说话人2：世界'], '说话人1：', '张三：')
    ).toEqual(['张三：你好', '说话人2：世界'])
    expect(collectSnapshotSpeakerIds([{ speaker_id: 1 }, { speaker_id: 0 }])).toEqual([0, 1])
    expect(mergeSpeakerSlots([], [3])).toEqual([0, 1, 2, 3])
  })

  it('merges a mistaken talker and folds extra slots back to 1/2/3', () => {
    const turns = remapTurnSpeakerIds(
      [
        { speakerId: 0, text: '甲', live: false, sentenceId: 0, startTime: 0 },
        { speakerId: 2, text: '乙', live: false, sentenceId: 1, startTime: 800 },
      ],
      2,
      0
    )
    expect(turns.map((turn) => turn.speakerId)).toEqual([0, 0])
    expect(speakerIdsAfterRemoving([0, 1, 2, 3], 3)).toEqual([0, 1, 2])
    expect(defaultSpeakerSlot(3)).toBe(0)
    expect(defaultSpeakerSlot(4)).toBe(1)
    expect(speakerIdsWithRemaps([0, 1, 2, 3], [3], { 3: 0 })).toEqual([0, 1, 2])
    expect(
      applySpeakerRemaps(
        [{ speakerId: 3, text: '误', live: false, sentenceId: 2, startTime: 1600 }],
        { 3: 0 }
      )[0]?.speakerId
    ).toBe(0)
  })
})

describe('linesFromEditedTranscript', () => {
  it('keeps paragraph breaks and caps line count', () => {
    expect(linesFromEditedTranscript('你好\r\n\n世界')).toEqual(['你好', '', '世界'])
    const many = Array.from({ length: 502 }, (_, i) => `L${i}`).join('\n')
    const capped = linesFromEditedTranscript(many)
    expect(capped).toHaveLength(500)
    expect(capped[0]).toBe('L2')
    expect(capped[499]).toBe('L501')
  })
})

describe('chat turns from snapshot', () => {
  it('keeps one row per speaker and formats ingest text', () => {
    const turns = turnsFromSnapshot([
      { text: '第一句', speaker_id: 0, sentence_id: 0, start_time: 0, final: true },
      { text: '第二句', speaker_id: 1, sentence_id: 1, start_time: 900, sentence_type: 0 },
    ])
    expect(turns).toEqual([
      { speakerId: 0, text: '第一句', live: false, sentenceId: 0, startTime: 0 },
      { speakerId: 1, text: '第二句', live: true, sentenceId: 1, startTime: 900 },
    ])
    expect(commitLiveTurns(turns)[1]?.live).toBe(false)
    expect(speakerDisplayName('说话人1：')).toBe('说话人1')
    expect(transcriptFromTurns(turns, (id) => (id === 0 ? '说话人1：' : '说话人2：'))).toBe(
      '说话人1：第一句\n说话人2：第二句'
    )
  })

  it('appends a later capture onto restored talker turns', () => {
    const restored = turnsFromSnapshot([
      { text: '上次说完了。', speaker_id: 0, sentence_id: 0, start_time: 0, final: true },
    ])
    const live = turnsFromSnapshot([
      { text: '今天继续。', speaker_id: 0, sentence_id: 0, start_time: 10, final: true },
    ])
    expect(mergeCaptureSnapshotTurns(restored, live)).toEqual([
      { speakerId: 0, text: '上次说完了。今天继续。', live: false, sentenceId: 0, startTime: 0 },
    ])
    expect(remainingVoiceNotesDurationMs(28_000, 60 * 60 * 1000)).toBe(60 * 60 * 1000 - 28_000)
    expect(remainingVoiceNotesDurationMs(0, 60_000)).toBe(60_000)
  })

  it('coalesces consecutive sentences from the same speaker', () => {
    expect(joinVoiceNotesSentences('Hello.', 'World.')).toBe('Hello. World.')
    expect(joinVoiceNotesSentences('你好。', '今天不错。')).toBe('你好。今天不错。')
    const coalesced = coalesceConsecutiveSpeakerTurns(
      turnsFromSnapshot([
        { text: '第一句。', speaker_id: 0, sentence_id: 0, start_time: 0, final: true },
        { text: '还在说。', speaker_id: 0, sentence_id: 1, start_time: 800, final: true },
        { text: '换人了', speaker_id: 1, sentence_id: 2, start_time: 1600, final: false },
      ])
    )
    expect(coalesced).toEqual([
      { speakerId: 0, text: '第一句。还在说。', live: false, sentenceId: 1, startTime: 0 },
      { speakerId: 1, text: '换人了', live: true, sentenceId: 2, startTime: 1600 },
    ])
  })
})

describe('splitVoiceNotesSnapshot', () => {
  it('splits steady sentences from the live one and labels speakers', () => {
    const { committed, live } = splitVoiceNotesSnapshot(
      [
        { text: '第一句', speaker_id: 0, final: true },
        { text: '第二句', speaker_id: 1, sentence_type: 0 },
      ],
      (n) => `说话人${n}：`
    )
    expect(committed).toEqual(['说话人1：第一句'])
    expect(live).toBe('说话人2：第二句')
  })

  it('ignores a non-array payload', () => {
    expect(splitVoiceNotesSnapshot({ sentence: 'x' }, () => 'S')).toEqual({
      committed: [],
      live: '',
    })
  })
})

describe('speakerAvatarGlyph', () => {
  it('uses a Latin initial or the first CJK character once a talker is named', () => {
    expect(speakerAvatarGlyph('', 1)).toBe('1')
    expect(speakerAvatarGlyph('Roy', 1)).toBe('R')
    expect(speakerAvatarGlyph('roy wang', 1)).toBe('R')
    expect(speakerAvatarGlyph('赵国庆', 2)).toBe('赵')
    expect(speakerAvatarGlyph('123', 3)).toBe('3')
  })
})

describe('parseVoiceNotesTranscript', () => {
  it('restores numbered talkers and custom names from saved markdown', () => {
    const parsed = parseVoiceNotesTranscript(
      ['Roy：你好', '说话人2：在吗', '赵国庆：在的'].join('\n')
    )
    expect(parsed.speakerNames).toEqual({ 0: 'Roy', 2: '赵国庆' })
    expect(parsed.turns.map((turn) => [turn.speakerId, turn.text])).toEqual([
      [0, '你好'],
      [1, '在吗'],
      [2, '在的'],
    ])
  })
})

describe('voiceNotes error toasts', () => {
  it('maps user-facing codes to i18n keys and stops the session', () => {
    expect(voiceNotesErrorI18nKey('tencent_auth')).toBe('auth.voiceNotes.tencentAuth')
    expect(voiceNotesErrorI18nKey('tencent_rps')).toBe('auth.voiceNotes.rateLimited')
    expect(voiceNotesErrorI18nKey('rate_limit')).toBe('auth.voiceNotes.rateLimited')
    expect(voiceNotesErrorI18nKey('too_large')).toBe('auth.voiceNotes.messageTooLarge')
    expect(voiceNotesErrorI18nKey('asr_config')).toBe('auth.voiceNotes.asrUnavailable')
    expect(voiceNotesErrorI18nKey('unknown')).toBeNull()
    expect(shouldStopVoiceNotesOnServerError('tencent_rps')).toBe(true)
    expect(shouldStopVoiceNotesOnServerError('rate_limit')).toBe(true)
    expect(shouldStopVoiceNotesOnServerError('too_large')).toBe(true)
  })
})
