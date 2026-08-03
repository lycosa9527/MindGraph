import { describe, expect, it } from 'vitest'

import {
  MIND_MAP_BRANCH_MAX_TEXT_WIDTH,
  MIND_MAP_TOPIC_MAX_TEXT_WIDTH,
  resolveMindMapBranchTextMaxWidthPx,
  resolveMindMapExportWrapColumnPx,
  resolveMindMapTopicTextMaxWidthPx,
  wrapMindMapExportLabelLines,
  wrapMindMapTextLines,
} from '@/utils/mindMapTextWrap'

describe('mindMapTextWrap', () => {
  it('keeps topic text maxWidth at 300', () => {
    expect(resolveMindMapTopicTextMaxWidthPx()).toBe(MIND_MAP_TOPIC_MAX_TEXT_WIDTH)
  })

  it('uses script-aware branch maxWidth for short CJK labels', () => {
    const max = resolveMindMapBranchTextMaxWidthPx('中心主题', 18, { fontWeight: 'bold' })
    expect(max).toBeGreaterThanOrEqual(MIND_MAP_BRANCH_MAX_TEXT_WIDTH)
    expect(max).toBeLessThanOrEqual(Math.round(MIND_MAP_BRANCH_MAX_TEXT_WIDTH * 1.5))
  })

  it('caps long branch wrap column at 200', () => {
    const long =
      '这是一段足够长的思维导图分支文字用来触发换行限制检查一二三四五六七八九十'
    const max = resolveMindMapBranchTextMaxWidthPx(long, 14)
    expect(max).toBe(MIND_MAP_BRANCH_MAX_TEXT_WIDTH)
  })

  it('export column is min(hostMax, boxInner)', () => {
    const col = resolveMindMapExportWrapColumnPx({
      role: 'branch',
      text: 'hello world',
      fontSize: 14,
      boxWidth: 100,
      paddingX: 12,
      borderWidth: 1.5,
    })
    // inner = 100 - 24 - 3 = 73
    expect(col).toBe(73)
  })

  it('export column does not exceed host text maxWidth', () => {
    const col = resolveMindMapExportWrapColumnPx({
      role: 'topic',
      text: '主题',
      fontSize: 18,
      fontWeight: 'bold',
      boxWidth: 500,
      paddingX: 12,
      borderWidth: 1.5,
    })
    expect(col).toBe(MIND_MAP_TOPIC_MAX_TEXT_WIDTH)
  })

  it('wraps long Latin tokens and keeps short labels on one line', () => {
    expect(wrapMindMapTextLines('中心主题', 200, { fontSize: 18, fontWeight: 'bold' })).toEqual([
      '中心主题',
    ])
    const lines = wrapMindMapTextLines('abcdefghijabcdefghij', 36, { fontSize: 14 })
    expect(lines.length).toBeGreaterThan(1)
  })

  it('prefers word boundaries for Latin text', () => {
    const lines = wrapMindMapTextLines('hello world', 40, { fontSize: 14 })
    expect(lines.some((line) => line.includes('hello') || line.includes('world'))).toBe(true)
    for (const line of lines) {
      expect(line === 'hel' || line === 'lo').toBe(false)
    }
  })

  it('keeps host-fitting labels single-line even in a tight minWidth box', () => {
    const lines = wrapMindMapExportLabelLines({
      role: 'branch',
      text: '中心主题',
      fontSize: 16,
      fontWeight: 'bold',
      boxWidth: 90,
      paddingX: 12,
      borderWidth: 1.5,
    })
    expect(lines).toEqual(['中心主题'])
  })
})
