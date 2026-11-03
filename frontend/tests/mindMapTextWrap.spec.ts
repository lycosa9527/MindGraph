import { describe, expect, it } from 'vitest'

import {
  MIND_MAP_BRANCH_MAX_TEXT_WIDTH,
  MIND_MAP_TOPIC_MAX_TEXT_WIDTH,
  estimateMindMapNumberedContentWidthPx,
  measureMindMapLabelWidthPx,
  measureMindMapNumberPrefixAdvancePx,
  measureThinkingMapLabelBlockPx,
  resolveMindMapBranchBodyMaxWidthPx,
  resolveMindMapBranchTextMaxWidthPx,
  resolveMindMapExportWrapColumnPx,
  resolveMindMapTopicTextMaxWidthPx,
  resolveThinkingMapDisplayMaxWidthPx,
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

  it('gives wider chrome to 第一章 than 1. or ①', () => {
    const fontSize = 16
    const chapter = measureMindMapNumberPrefixAdvancePx('第一章', fontSize)
    const circled = measureMindMapNumberPrefixAdvancePx('①', fontSize)
    const decimal = measureMindMapNumberPrefixAdvancePx('1.', fontSize)
    expect(chapter).toBeGreaterThan(circled)
    expect(chapter).toBeGreaterThan(decimal)
    expect(estimateMindMapNumberedContentWidthPx('分支1', '第一章', fontSize)).toBeGreaterThan(
      estimateMindMapNumberedContentWidthPx('分支1', '1.', fontSize)
    )
  })

  it('shrinks the editable body wrap budget when a numbering prefix is present', () => {
    const label = 'china'
    const withoutPrefix = resolveMindMapBranchTextMaxWidthPx(label, 14)
    const withPrefix = resolveMindMapBranchBodyMaxWidthPx(label, '1.1.1.1.1', 14)
    expect(withPrefix).toBeLessThan(withoutPrefix)
    expect(withPrefix).toBeGreaterThanOrEqual(48)
  })

  it('keeps a CJK label that fits the script-aware column on one line', () => {
    const text = '香甜多汁的红色果实'
    const block = measureThinkingMapLabelBlockPx(text, 16, 200)
    expect(block.lineCount).toBe(1)
    expect(resolveThinkingMapDisplayMaxWidthPx(text, 16, 200)).toBeGreaterThanOrEqual(200)
  })

  it('wraps a long label at the map cap and balances the lines', () => {
    const text = '香甜多汁的红色果实'.repeat(6)
    const block = measureThinkingMapLabelBlockPx(text, 16, 200)
    expect(block.lineCount).toBeGreaterThan(1)
    expect(block.width).toBeLessThanOrEqual(200)
    expect(resolveThinkingMapDisplayMaxWidthPx(text, 16, 350)).toBeLessThanOrEqual(350)
    const lines = block.lineCount
    const widerCap = measureThinkingMapLabelBlockPx(text, 16, 350)
    expect(widerCap.lineCount).toBeLessThanOrEqual(lines)
  })

  it('caps long branch wrap column at 200', () => {
    const long = '这是一段足够长的思维导图分支文字用来触发换行限制检查一二三四五六七八九十'
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

  it('balances a CJK label so the last line is not one character', () => {
    const text = '思维导图自动换行测试'
    const fontSize = 16
    const headWidth = measureMindMapLabelWidthPx(text.slice(0, -1), fontSize)
    const lines = wrapMindMapTextLines(text, headWidth, { fontSize })
    expect(lines.length).toBe(2)
    expect([...lines[lines.length - 1]].length).toBeGreaterThan(1)
    expect(lines.join('')).toBe(text)
  })

  it('keeps a Latin prefix on the same line as the following CJK', () => {
    const fontSize = 16
    const text = 'AI承担代码、计算和建议，专家负责测量、解释和下一步'
    const lines = wrapMindMapTextLines(text, 200, { fontSize })
    expect(lines.join('')).toBe(text)
    expect(lines[0]?.startsWith('AI')).toBe(true)
    expect((lines[0]?.length ?? 0) > 2).toBe(true)
    expect(lines.length).toBeLessThan(3)
  })

  it('keeps a percent or number with the CJK that follows it', () => {
    const fontSize = 16
    const percent = '77%的分析师在解释中重复智能体论点，有时逐字'
    const percentLines = wrapMindMapTextLines(percent, 200, { fontSize })
    expect(percentLines.join('')).toBe(percent)
    expect(percentLines[0]?.startsWith('77%')).toBe(true)
    expect(percentLines[0]).not.toBe('77%')

    const numbered = '招募61名因果推断专业分析师，50人使用AI智能体'
    const numberedLines = wrapMindMapTextLines(numbered, 200, { fontSize })
    expect(numberedLines.join('')).toBe(numbered)
    expect(numberedLines[0]?.startsWith('招募61')).toBe(true)
    expect(numberedLines[0]).not.toBe('招募61')
  })

  it('keeps a Latin prefix on the same line as the following kana', () => {
    const text = 'AIこんにちは世界の説明ですよ'
    const lines = wrapMindMapTextLines(text, 120, { fontSize: 16 })
    expect(lines.join('')).toBe(text)
    expect(lines[0]?.startsWith('AI')).toBe(true)
    expect(lines[0]).not.toBe('AI')
    expect(lines.length).toBeGreaterThan(1)
  })

  it('prefers word boundaries for Latin text', () => {
    const lines = wrapMindMapTextLines('hello world', 40, { fontSize: 14 })
    expect(lines.some((line) => line.includes('hello') || line.includes('world'))).toBe(true)
    for (const line of lines) {
      expect(line === 'hel' || line === 'lo').toBe(false)
    }
  })

  it('export wrap follows the canvas column and keeps Latin with the following CJK', () => {
    const text = 'AI承担代码、计算和建议，专家负责测量、解释和下一步'
    const lines = wrapMindMapExportLabelLines({
      role: 'branch',
      text,
      fontSize: 16,
      boxWidth: 224,
      paddingX: 12,
      borderWidth: 0,
    })
    expect(lines.join('')).toBe(text)
    expect(lines[0]?.startsWith('AI')).toBe(true)
    expect(lines[0]).not.toBe('AI')
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
