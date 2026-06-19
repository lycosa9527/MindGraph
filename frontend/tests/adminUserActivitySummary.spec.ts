/** Vitest — admin user activity summary formatting. */

import { describe, expect, it } from 'vitest'

import {
  activitySourceLabel,
  formatAdminUserActivitySummary,
  type ActivitySummaryLabels,
} from '@/utils/adminUserActivitySummary'

const labels: ActivitySummaryLabels = {
  ask: 'Q: ',
  answer: 'A: ',
  generate: 'Generated',
  save: 'Saved',
  dingtalkGenerate: 'DingTalk diagram',
  sourceMindgraph: 'MindGraph',
  sourceMindmate: 'MindMate',
  sourceDingtalk: 'DingTalk',
  failedSuffix: ' (failed)',
}

describe('formatAdminUserActivitySummary', () => {
  it('formats chat turn with prompt and reply', () => {
    const summary = formatAdminUserActivitySummary(
      {
        source: 'mindmate',
        action: 'chat_turn',
        promptPreview: 'How to teach?',
        replyPreview: 'Start with goals',
      },
      labels,
      'en'
    )
    expect(summary).toContain('Q: How to teach?')
    expect(summary).toContain('A: Start with goals')
  })

  it('formats diagram generate with type and title', () => {
    const summary = formatAdminUserActivitySummary(
      {
        source: 'mindgraph',
        action: 'diagram_generate',
        title: 'Photosynthesis',
        diagramType: 'mind_map',
      },
      labels,
      'zh'
    )
    expect(summary).toContain('Generated')
    expect(summary).toContain('思维导图')
    expect(summary).toContain('Photosynthesis')
  })

  it('labels sources', () => {
    expect(activitySourceLabel('dingtalk', labels)).toBe('DingTalk')
  })

  it('uses English diagram type labels', () => {
    const summary = formatAdminUserActivitySummary(
      {
        source: 'mindgraph',
        action: 'diagram_generate',
        title: 'Topic',
        diagramType: 'bubble_map',
      },
      labels,
      'en'
    )
    expect(summary).toContain('Bubble map')
  })

  it('uses distinct verb for dingtalk diagrams', () => {
    const summary = formatAdminUserActivitySummary(
      {
        source: 'dingtalk',
        action: 'dingtalk_diagram',
        title: 'Weekly plan',
        diagramType: 'mind_map',
      },
      labels,
      'en'
    )
    expect(summary).toContain('DingTalk diagram')
    expect(summary).not.toContain('Generated')
  })
})
