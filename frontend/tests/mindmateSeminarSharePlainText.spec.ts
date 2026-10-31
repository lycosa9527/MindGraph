import { describe, expect, it } from 'vitest'

import { SEMINAR_SUMMARY_MARKER, seminarMinutesMessage } from '@/utils/mindmateSeminarCards'
import { minutesFieldText, parseMinutesDraft } from '@/utils/mindmateSeminarMinutes'
import { formatSeminarShareLine } from '@/utils/mindmateSeminarShare'

const t = (key: string, named?: Record<string, string | number>) => {
  const map: Record<string, string> = {
    'mindmate.summary.cardKicker': '教研纪要',
    'mindmate.summary.covered': '覆盖时间',
    'mindmate.summary.speakers': '发言人',
    'mindmate.summary.observers': '到场观摩',
    'mindmate.summary.section.goals': '对照目标',
    'mindmate.summary.section.consensus': '共识',
    'mindmate.summary.section.open': '分歧与未决',
    'mindmate.summary.section.materials': '用到的材料',
    'mindmate.summary.section.tasks': '待办',
    'mindmate.summary.section.quotes': '精华摘录',
    'mindmate.shareSheet.imageAttachment': '[图片]',
    'mindmate.shareSheet.imageNamed': '[图片] {name}',
    'mindmate.shareSheet.voiceAttachment': '[语音]',
    'mindmate.shareSheet.fileAttachment': '[附件] {name}',
    'mindmate.shareSheet.fileFallback': '文件',
    'mindmate.shareSheet.diagramAttachment': '思维图示',
    'mindmate.artifacts.diagramFallback': 'MindGraph 图',
    'mindmate.briefCard.kicker': 'Seminar brief',
  }
  let text = map[key] || key
  if (named) {
    for (const [name, value] of Object.entries(named)) {
      text = text.replace(`{${name}}`, String(value))
    }
  }
  return text
}

describe('formatSeminarShareLine', () => {
  it('turns seminar minutes into a readable share bubble, not raw JSON', () => {
    const content = seminarMinutesMessage({
      scope: '全部消息 · 共 6 条',
      body: '',
      topic: '测试教研会',
      timeRange: '10/30 21:29 – 10/30 21:46',
      speakers: [{ name: '王雅萱', role: '组长' }],
      observers: [],
      goals: [{ goal: '了解如何设计认知冲突', status: 'met' }],
      consensus: ['先抛问题再给概念'],
      open: [],
      materials: ['课件.pdf'],
      tasks: ['下周试讲一轮'],
      quotes: ['“用冲突带动讨论”'],
      author: '教研助手',
      structured: true,
    })
    const line = formatSeminarShareLine(content, t)
    expect(line.kind).toBe('summary')
    expect(line.badge).toBe('教研纪要')
    expect(line.content).not.toContain(SEMINAR_SUMMARY_MARKER)
    expect(line.content).not.toContain('"topic"')
    expect(line.content).toContain('测试教研会')
    expect(line.content).toContain('王雅萱（组长）')
    expect(line.content).toContain('先抛问题再给概念')
  })

  it('labels hash image uploads as [图片] instead of raw filenames', () => {
    const line = formatSeminarShareLine(
      '图片你看看\n[[sf:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee|452aa5af5a7335313e6930894865c1a9.png]]',
      t
    )
    expect(line.kind).toBe('text')
    expect(line.content).toContain('图片你看看')
    expect(line.content).toContain('[图片]')
    expect(line.content).not.toContain('452aa5af5a7335313e6930894865c1a9.png')
  })

  it('keeps object materials from becoming [object Object]', () => {
    const text = minutesFieldText([{ name: '研讨提纲.docx' }, { title: '板书照片' }, '补充材料'])
    expect(text).not.toContain('[object Object]')
    const draft = parseMinutesDraft(
      JSON.stringify({
        materials: [{ name: '研讨提纲.docx' }, { file: '板书.png' }],
        consensus: ['共识一'],
      })
    )
    expect(draft?.materials).toEqual(['研讨提纲.docx', '板书.png'])
  })
})
