import { describe, expect, it } from 'vitest'

import {
  collectSeminarDiagramArtifacts,
  collectSeminarDocumentArtifacts,
} from '@/utils/mindmateSeminarArtifacts'
import {
  seminarBriefIsComplete,
  seminarBriefMissing,
  seminarBriefSectionFilled,
  seminarSeedFromBrief,
} from '@/utils/mindmateSeminarBrief'
import {
  parseSeminarBriefCard,
  parseSeminarSummaryCard,
  seminarSummaryMessage,
} from '@/utils/mindmateSeminarCards'
import { seminarMessageFileToken, splitSeminarMessageFiles } from '@/utils/mindmateSeminarFolder'
import { seminarTitleFromTopic } from '@/utils/mindmateSeminarHome'

describe('seminarTitleFromTopic', () => {
  it('keeps a short topic and trims a long one', () => {
    expect(seminarTitleFromTopic('  平行四边形  认知冲突  ')).toBe('平行四边形 认知冲突')
    expect(seminarTitleFromTopic('a'.repeat(50))).toBe('a'.repeat(40))
  })
})

describe('seminarBrief', () => {
  const labels = {
    topic: '教研主题',
    goals: '教研目标',
    participants: '参与人员',
    resources: '资源准备',
    roleLabels: {
      leader: '组长',
      leadPrep: '主备人',
      coPrep: '辅备人',
      expert: '专家',
      researcher: '教研员',
      observer: '观摩学习',
      none: '未分配',
    },
    visibilityOrg: '校内教研',
    visibilityNetwork: '跨校教研',
    skipRoles: '暂不进行角色分配',
    skipResources: '暂不上传',
    pendingConsent: '待对方同意',
  }

  it('requires a topic and at least one invitee', () => {
    expect(
      seminarBriefMissing(
        {
          topic: '  ',
          goals: ['', '  '],
          visibility: 'organization',
          participants: [],
          skipRoles: false,
          resourceFiles: [],
          skipResources: false,
        },
        1
      )
    ).toEqual(['topic', 'participants'])
  })

  it('treats host-only roster as incomplete participants', () => {
    const hostOnly = {
      topic: '主题',
      goals: ['目标'],
      visibility: 'organization' as const,
      participants: [{ userId: 1, name: '我', role: 'leader' as const, source: 'school' as const }],
      skipRoles: false,
      resourceFiles: [],
      skipResources: false,
    }
    expect(seminarBriefIsComplete(hostOnly, 1)).toBe(false)
    expect(seminarBriefSectionFilled(hostOnly, 'participants', 1)).toBe(false)
    expect(seminarBriefMissing(hostOnly, 1)).toEqual(['participants'])
    expect(
      seminarBriefSectionFilled(
        {
          ...hostOnly,
          participants: [
            ...hostOnly.participants,
            { userId: 2, name: '王老师', role: 'observer' as const, source: 'school' as const },
          ],
        },
        'participants',
        1
      )
    ).toBe(true)
    expect(seminarBriefIsComplete({ ...hostOnly, skipResources: true }, 1)).toBe(false)
    expect(seminarBriefSectionFilled(hostOnly, 'resources')).toBe(false)
    expect(seminarBriefSectionFilled({ ...hostOnly, skipResources: true }, 'resources')).toBe(true)
  })

  it('builds a seeded brief from the filled lines', () => {
    const brief = {
      topic: '  平行四边形认知冲突  ',
      goals: [' 找出冲突点 ', ''],
      visibility: 'organization' as const,
      participants: [
        { userId: 2, name: '王老师', role: 'leader' as const, source: 'school' as const },
      ],
      skipRoles: false,
      resourceFiles: [new File(['x'], '课堂实录.pdf', { type: 'application/pdf' })],
      skipResources: false,
    }
    expect(seminarSeedFromBrief(brief, labels)).toEqual({
      title: '平行四边形认知冲突',
      seedMessages: [
        {
          role: 'user',
          content: `[[seminar-brief]]\n${[
            '教研主题\n平行四边形认知冲突',
            '教研目标\n1. 找出冲突点',
            '参与人员\n校内教研',
            '1. 王老师（组长）',
            '资源准备\n1. 课堂实录.pdf',
          ].join('\n\n')}`,
        },
      ],
    })
  })

  it('marks external phone invitees as awaiting consent in the seed', () => {
    const brief = {
      topic: '跨校主题',
      goals: ['协作'],
      visibility: 'network' as const,
      participants: [
        {
          userId: 9,
          name: '李老师',
          role: 'observer' as const,
          source: 'external' as const,
        },
      ],
      skipRoles: false,
      resourceFiles: [],
      skipResources: true,
    }
    const seeded = seminarSeedFromBrief(brief, labels)
    expect(seeded.seedMessages[0]?.content).toContain('1. 李老师（观摩学习）（待对方同意）')
  })
})

describe('collectSeminarDiagramArtifacts', () => {
  it('collects each preview once and keeps the image label', () => {
    const messages = [
      {
        id: 3,
        content: '先看 ![认知冲突](/temp_images/dingtalk_ab12cd34_171000.png)',
      },
      {
        id: 4,
        content:
          '重复 ![认知冲突](https://x/temp_images/dingtalk_ab12cd34_171000.png) 和 ![另一张](/temp_images/dingtalk_00112233_2.png)',
      },
    ]
    expect(collectSeminarDiagramArtifacts(messages)).toEqual([
      {
        previewId: 'ab12cd34',
        label: '认知冲突',
        messageId: 3,
        imagePath: '/api/temp_images/dingtalk_ab12cd34_171000.png',
      },
      {
        previewId: '00112233',
        label: '另一张',
        messageId: 4,
        imagePath: '/api/temp_images/dingtalk_00112233_2.png',
      },
    ])
  })
})

describe('splitSeminarMessageFiles', () => {
  it('lifts chat attachments out of the visible text', () => {
    const token = seminarMessageFileToken('11111111-1111-1111-1111-111111111111', '讲义].pdf')
    const split = splitSeminarMessageFiles(`看一下\n\n${token}`)
    expect(split.text).toBe('看一下')
    expect(split.files).toEqual([
      { id: '11111111-1111-1111-1111-111111111111', filename: '讲义].pdf' },
    ])
  })
})

describe('collectSeminarDocumentArtifacts', () => {
  it('collects chat document links and skips diagram previews', () => {
    const messages = [
      {
        id: 1,
        content:
          '导出 [教研纪要.pdf](https://cdn.example/notes.pdf) 与 https://cdn.example/outline.docx',
      },
      {
        id: 2,
        content: '图 ![示意](/temp_images/dingtalk_aabbccdd_1.png) 不是文档',
      },
    ]
    expect(collectSeminarDocumentArtifacts(messages)).toEqual([
      {
        id: 'https://cdn.example/notes.pdf',
        title: '教研纪要.pdf',
        url: 'https://cdn.example/notes.pdf',
        messageId: 1,
      },
      {
        id: 'https://cdn.example/outline.docx',
        title: 'outline.docx',
        url: 'https://cdn.example/outline.docx',
        messageId: 1,
      },
    ])
  })

  it('leaves conversation file tokens on the message until someone shelves them', () => {
    const token = seminarMessageFileToken('22222222-2222-2222-2222-222222222222', '课堂片段.webm')
    expect(collectSeminarDocumentArtifacts([{ id: 8, content: `先听这段\n\n${token}` }])).toEqual(
      []
    )
  })
})

describe('seminar cards', () => {
  it('reads a legacy brief bubble as a card', () => {
    const card = parseSeminarBriefCard(
      [
        '教研主题',
        '测试',
        '',
        '教研目标',
        '1. 第一个目标是第一个目标是',
        '2. 第一个目标是',
        '',
        '参与人员',
        '校内教研',
        '',
        '1. 王雅萱（组长）',
        '2. 李思琦（观摩学习）',
        '',
        '资源准备',
        '1. 中小学课程思政评价指标研究综述.docx',
        '2. 大中小学思政课一体化评价体系构建的导向',
      ].join('\n')
    )
    expect(card).toEqual({
      topic: '测试',
      goals: ['第一个目标是第一个目标是', '第一个目标是'],
      visibility: '校内教研',
      participants: [
        { name: '王雅萱', role: '组长' },
        { name: '李思琦', role: '观摩学习' },
      ],
      resources: ['中小学课程思政评价指标研究综述.docx', '大中小学思政课一体化评价体系构建的导向'],
    })
  })

  it('round-trips a summary card and ignores it as a brief', () => {
    const content = seminarSummaryMessage('全部消息', '结论：先改导入。')
    expect(parseSeminarBriefCard(content)).toBeNull()
    expect(parseSeminarSummaryCard(content)).toEqual({
      scope: '全部消息',
      body: '结论：先改导入。',
      topic: '',
      timeRange: '',
      speakers: [],
      observers: [],
      goals: [],
      consensus: [],
      open: [],
      materials: [],
      tasks: [],
      quotes: [],
      author: '',
      structured: false,
    })
  })
})
