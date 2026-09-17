import { describe, expect, it } from 'vitest'

import { stripMindmateDiagramIdComments } from '@/utils/mindmateDiagramMeta'
import {
  isTeachingInstructionOutputs,
  isTeachingInstructionReply,
  parseTeachingInstructionKind,
  stripTeachingDesignFlags,
} from '@/utils/mindmateTeachingDesignFlag'

describe('mindmateTeachingDesignFlag', () => {
  it('parses HTML comment and bracket markers', () => {
    expect(
      parseTeachingInstructionKind('正文\n<!-- mg-reply-kind:teaching_instruction -->')
    ).toBe('teaching_instruction')
    expect(isTeachingInstructionReply('正文\n[mg-reply-kind:teaching_instruction]')).toBe(true)
    expect(isTeachingInstructionReply('普通问答')).toBe(false)
  })

  it('reads workflow outputs', () => {
    expect(isTeachingInstructionOutputs({ mg_reply_kind: 'teaching_instruction' })).toBe(true)
    expect(isTeachingInstructionOutputs({ export_word_template: true })).toBe(true)
    expect(isTeachingInstructionOutputs({ other: 1 })).toBe(false)
  })

  it('strips both markers from display markdown', () => {
    const raw =
      '课例正文\n<!-- mg-reply-kind:teaching_instruction -->\n[mg-reply-kind:teaching_instruction]'
    expect(stripTeachingDesignFlags(raw)).toBe('课例正文')
    expect(stripMindmateDiagramIdComments(raw)).toBe('课例正文')
    expect(stripMindmateDiagramIdComments(raw)).not.toContain('mg-reply-kind')
  })

  it('strips incomplete trailing markers while streaming', () => {
    expect(stripTeachingDesignFlags('课例\n<!-- mg-reply-kind:teaching_instru')).toBe('课例')
    expect(stripTeachingDesignFlags('课例\n[mg-reply-kind:teaching_')).toBe('课例')
  })
})
