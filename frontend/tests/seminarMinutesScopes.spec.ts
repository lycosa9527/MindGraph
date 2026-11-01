import { describe, expect, it } from 'vitest'

import type { SeminarHighlight } from '@/composables/mindmate/mindmateSeminarChrome'
import { seminarSummaryMessage } from '@/utils/mindmateSeminarCards'
import {
  type MinutesSource,
  latestSummaryStamp,
  selectMinutesSources,
} from '@/utils/mindmateSeminarMinutes'

function row(
  partial: Partial<MinutesSource> & Pick<MinutesSource, 'key' | 'content'>
): MinutesSource {
  return {
    author: '王雅萱',
    preview: partial.content,
    createdAt: '2026-11-01T10:00:00+08:00',
    messageId: null,
    senderId: 7,
    assistant: false,
    ...partial,
  }
}

const sources: MinutesSource[] = [
  row({
    key: 'early',
    content: '先改青柠导入',
    createdAt: '2026-11-01T09:00:00+08:00',
    messageId: 1,
  }),
  row({
    key: 'late',
    content: '琥珀作业改到周五',
    createdAt: '2026-11-01T11:00:00+08:00',
    messageId: 2,
    author: '董长华',
  }),
  row({
    key: 'marked',
    content: '板书要留白',
    createdAt: '2026-11-01T11:30:00+08:00',
    messageId: 3,
  }),
]

const highlight: SeminarHighlight = {
  id: 'h1',
  text: '板书要留白',
  authorName: '王雅萱',
  messageId: 3,
  createdAt: '2026-11-01T11:31:00+08:00',
}

describe('seminar minutes ranges', () => {
  it('keeps every chat line for 全部消息', () => {
    const picked = selectMinutesSources(sources, 'all', {}, [], '')
    expect(picked.map((item) => item.key)).toEqual(['early', 'late', 'marked'])
  })

  it('keeps only lines after the last minutes for 自上次纪要之后', () => {
    const cutoff = '2026-11-01T10:30:00+08:00'
    const picked = selectMinutesSources(sources, 'since', {}, [], cutoff)
    expect(picked.map((item) => item.key)).toEqual(['late', 'marked'])
  })

  it('treats a seminar with no earlier minutes as all new lines', () => {
    const picked = selectMinutesSources(sources, 'since', {}, [], '')
    expect(picked.map((item) => item.key)).toEqual(['early', 'late', 'marked'])
  })

  it('keeps only marked lines for 已设为精华的消息', () => {
    const picked = selectMinutesSources(sources, 'highlights', {}, [highlight], '')
    expect(picked.map((item) => item.key)).toEqual(['marked'])
  })

  it('keeps only checked lines for 自选消息', () => {
    const picked = selectMinutesSources(sources, 'part', { late: true }, [highlight], '')
    expect(picked.map((item) => item.key)).toEqual(['late'])
  })

  it('reads the cutoff from the latest minutes card', () => {
    const stamp = latestSummaryStamp([
      {
        role: 'assistant',
        content: seminarSummaryMessage('全部消息', '第一份'),
        created_at: '2026-11-01T10:00:00+08:00',
      },
      {
        role: 'user',
        content: '普通消息',
        created_at: '2026-11-01T12:00:00+08:00',
      },
      {
        role: 'assistant',
        content: seminarSummaryMessage('自上次纪要之后', '第二份'),
        created_at: '2026-11-01T11:00:00+08:00',
      },
    ])
    expect(stamp).toBe('2026-11-01T11:00:00+08:00')
  })
})
