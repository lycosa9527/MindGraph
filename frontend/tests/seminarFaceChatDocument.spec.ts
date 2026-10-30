import { describe, expect, it } from 'vitest'

import {
  composeFaceChatDocument,
  faceChatFilename,
  isSeminarFaceChatFile,
} from '@/utils/seminarFaceChatDocument'

describe('seminar face-chat documents', () => {
  it('names the archive from the Beijing clock', () => {
    const name = faceChatFilename(new Date('2026-10-30T10:06:00.000Z'), '面聊记录')
    expect(name).toBe('面聊记录-20261030-1806.md')
  })

  it('keeps a transcript-only file until a summary exists', () => {
    expect(
      composeFaceChatDocument({
        transcript: '说话人1：你好',
        summary: '',
        summaryHeading: '面聊总结',
        notesHeading: '面聊记录',
      })
    ).toBe('说话人1：你好')
  })

  it('places the summary above the transcript', () => {
    expect(
      composeFaceChatDocument({
        transcript: '说话人1：你好',
        summary: '讨论了导入问题。',
        summaryHeading: '面聊总结',
        notesHeading: '面聊记录',
      })
    ).toBe('# 面聊总结\n\n讨论了导入问题。\n\n# 面聊记录\n\n说话人1：你好')
  })

  it('tells face-chat files apart from other artifacts', () => {
    expect(isSeminarFaceChatFile({ kind: 'face_chat' })).toBe(true)
    expect(isSeminarFaceChatFile({ kind: '' })).toBe(false)
    expect(isSeminarFaceChatFile({})).toBe(false)
  })
})
