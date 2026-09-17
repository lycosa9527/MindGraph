import { describe, expect, it } from 'vitest'

import {
  collabAssistantLibraryDiagramId,
  collabMessageRowKey,
  collabMessagesForShareExport,
  displayMindmateCollabContent,
  lastFinishedAssistantIndex,
  nextCollabFeedback,
  previousCollabUserPrompt,
  shouldShowCollabWordTemplateExport,
} from '@/utils/mindmateCollabDisplay'

const TEACHING = '课例正文\n<!-- mg-reply-kind:teaching_instruction -->\n[mg-reply-kind:teaching_instruction]'

describe('mindmateCollabDisplay', () => {
  it('keeps peer text unchanged and strips MindMate reply-kind markers', () => {
    expect(displayMindmateCollabContent('大家好', 'user')).toBe('大家好')
    expect(displayMindmateCollabContent(TEACHING, 'assistant')).toBe('课例正文')
    expect(displayMindmateCollabContent(TEACHING, 'assistant')).not.toContain('mg-reply-kind')
  })

  it('shows Word export only on finished teaching-instruction replies', () => {
    expect(
      shouldShowCollabWordTemplateExport({ role: 'assistant', content: TEACHING })
    ).toBe(true)
    expect(
      shouldShowCollabWordTemplateExport({
        role: 'assistant',
        content: TEACHING,
        streaming: true,
      })
    ).toBe(false)
    expect(
      shouldShowCollabWordTemplateExport({ role: 'user', content: TEACHING })
    ).toBe(false)
    expect(
      shouldShowCollabWordTemplateExport({ role: 'assistant', content: '普通问答' })
    ).toBe(false)
  })

  it('reads library diagram id from finished assistant markdown only', () => {
    const withId = '见图\n<!-- mg-diagram-id:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee -->'
    expect(
      collabAssistantLibraryDiagramId({ role: 'assistant', content: withId })
    ).toBe('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
    expect(
      collabAssistantLibraryDiagramId({ role: 'assistant', content: withId, streaming: true })
    ).toBeNull()
    expect(collabAssistantLibraryDiagramId({ role: 'user', content: withId })).toBeNull()
  })

  it('finds the previous user prompt for an assistant row', () => {
    const rows = [
      { role: 'user' as const, content: '先聊一下' },
      { role: 'user' as const, content: '请写教学设计' },
      { role: 'assistant' as const, content: TEACHING },
    ]
    expect(previousCollabUserPrompt(rows, 2)).toBe('请写教学设计')
    expect(previousCollabUserPrompt(rows, 0)).toBeUndefined()
  })

  it('keys rows by server id then client key', () => {
    expect(collabMessageRowKey({ id: 12, role: 'user' }, 0)).toBe('id-12')
    expect(collabMessageRowKey({ clientKey: 'ck-1', role: 'user' }, 3)).toBe('ck-1')
    expect(collabMessageRowKey({ role: 'assistant' }, 4)).toBe('msg-4-assistant')
  })

  it('toggles like/dislike the same way as 1:1', () => {
    expect(nextCollabFeedback(undefined, 'like')).toBe('like')
    expect(nextCollabFeedback('like', 'like')).toBeNull()
    expect(nextCollabFeedback('like', 'dislike')).toBe('dislike')
  })

  it('picks the last finished assistant for the always-visible bar', () => {
    expect(
      lastFinishedAssistantIndex([
        { role: 'user', content: '问' },
        { role: 'assistant', content: '答一' },
        { role: 'assistant', content: '答二', streaming: true },
      ]),
    ).toBe(1)
  })

  it('maps seminar rows to share-export messages without stream stubs', () => {
    const rows = collabMessagesForShareExport([
      { id: 1, role: 'user', content: '请写教学设计' },
      { role: 'assistant', content: TEACHING, streaming: true },
      { id: 2, role: 'assistant', content: TEACHING },
    ])
    expect(rows).toHaveLength(2)
    expect(rows[1].content).toBe('课例正文')
    expect(rows[1].id).toBe('id-2')
  })
})
