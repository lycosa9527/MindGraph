import { describe, expect, it } from 'vitest'

import {
  estimateNumberedBranchWidth,
  measureNumberedBranchHeight,
} from '@/stores/specLoader/mindMap'
import type { Connection, DiagramNode } from '@/types'
import {
  buildMindMapBranchNumberMap,
  formatAlphaNumber,
  formatChineseArticleUnit,
  formatChineseChapterUnit,
  formatChineseNumber,
  formatCircledNumber,
  formatMindMapBranchPrefix,
  formatMindMapOutlinePrefix,
  mindMapClockwiseL1Index,
  isMindMapBranchNumberingEnabled,
  joinMindMapBranchDisplayText,
  resolveMindMapBranchNumberingNested,
  resolveMindMapBranchNumberingPrefix,
  stripMatchingBranchNumberPrefix,
  invalidateMindMapBranchNumberMapCache,
  mindMapBranchNumberMapFromData,
  writeMindMapNumberingLiveFields,
} from '@/utils/mindMapBranchNumbering'

function node(
  id: string,
  text: string,
  type: DiagramNode['type'] = 'branch',
  x = 0,
  y = 0
): DiagramNode {
  return { id, text, type, position: { x, y } }
}

function edge(id: string, source: string, target: string): Connection {
  return { id, source, target }
}

describe('mindMapClockwiseL1Index', () => {
  it('numbers right top→bottom then left bottom→top', () => {
    expect(mindMapClockwiseL1Index('right', 0, 2, 2)).toBe(1)
    expect(mindMapClockwiseL1Index('right', 1, 2, 2)).toBe(2)
    expect(mindMapClockwiseL1Index('left', 1, 2, 2)).toBe(3)
    expect(mindMapClockwiseL1Index('left', 0, 2, 2)).toBe(4)
  })
})

describe('mindMapBranchNumbering glyphs', () => {
  it('formats chinese 1–99 then falls back', () => {
    expect(formatChineseNumber(1)).toBe('一')
    expect(formatChineseNumber(10)).toBe('十')
    expect(formatChineseNumber(11)).toBe('十一')
    expect(formatChineseNumber(20)).toBe('二十')
    expect(formatChineseNumber(21)).toBe('二十一')
    expect(formatChineseNumber(99)).toBe('九十九')
    expect(formatChineseNumber(100)).toBe('100')
  })

  it('formats circled 1–20 then paren fallback', () => {
    expect(formatCircledNumber(1)).toBe('①')
    expect(formatCircledNumber(20)).toBe('⑳')
    expect(formatCircledNumber(21)).toBe('(21)')
  })

  it('formats letters A–Z then AA', () => {
    expect(formatAlphaNumber(1, true)).toBe('A')
    expect(formatAlphaNumber(26, true)).toBe('Z')
    expect(formatAlphaNumber(27, true)).toBe('AA')
    expect(formatAlphaNumber(1, false)).toBe('a')
  })

  it('formats L1 glyph vs ISO outline children', () => {
    expect(formatMindMapBranchPrefix([1], 'decimal', 'outline')).toBe('1.')
    expect(formatMindMapBranchPrefix([1, 1], 'decimal', 'outline')).toBe('1.1')
    expect(formatMindMapBranchPrefix([1, 2], 'chinese', 'outline')).toBe('1.2')
    expect(formatMindMapOutlinePrefix([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])).toBe(
      '1.2.3.4.5.6.7.8.9.10'
    )
    expect(formatMindMapBranchPrefix([2, 1], 'upperAlpha', 'lowerAlpha')).toBe('a.')
  })

  it('formats 章 / 节 / 段 by depth and keeps outline on L2+ when nested is ISO', () => {
    expect(formatChineseChapterUnit(1, 1)).toBe('第一章')
    expect(formatChineseChapterUnit(2, 2)).toBe('第二节')
    expect(formatChineseChapterUnit(3, 3)).toBe('第三段')
    expect(formatChineseChapterUnit(1, 4)).toBe('第一条')
    expect(formatChineseChapterUnit(1, 7)).toBe('第一点')
    expect(formatMindMapBranchPrefix([1], 'chineseChapter', 'outline')).toBe('第一章')
    expect(formatMindMapBranchPrefix([2], 'chineseChapter', 'outline')).toBe('第二章')
    expect(formatMindMapBranchPrefix([1, 1], 'chineseChapter', 'outline')).toBe('1.1')
    expect(formatMindMapBranchPrefix([1, 2], 'chineseChapter', 'chineseChapter')).toBe('第二节')
    expect(formatMindMapBranchPrefix([1, 1, 3], 'chineseChapter', 'chineseChapter')).toBe(
      '第三段'
    )
    expect(formatMindMapBranchPrefix([3, 2, 4], 'decimal', 'chineseChapter')).toBe('第四段')
  })

  it('formats 条 / 款 / 项 / 目 for contract and statute clauses', () => {
    expect(formatChineseArticleUnit(1, 1)).toBe('第一条')
    expect(formatChineseArticleUnit(2, 2)).toBe('第二款')
    expect(formatChineseArticleUnit(3, 3)).toBe('第三项')
    expect(formatChineseArticleUnit(1, 4)).toBe('第一目')
    expect(formatChineseArticleUnit(1, 5)).toBe('第一点')
    expect(formatMindMapBranchPrefix([1], 'chineseArticle', 'outline')).toBe('第一条')
    expect(formatMindMapBranchPrefix([1, 2], 'chineseArticle', 'outline')).toBe('1.2')
    expect(formatMindMapBranchPrefix([1, 2], 'chineseArticle', 'chineseArticle')).toBe('第二款')
    expect(formatMindMapBranchPrefix([1, 1, 3], 'chineseArticle', 'chineseArticle')).toBe(
      '第三项'
    )
  })
})

describe('mindMapBranchNumbering map', () => {
  it('skips the topic and numbers L1 clockwise then children', () => {
    const nodes: DiagramNode[] = [
      node('topic', '中心', 'topic', 0, 100),
      node('branch-r-1-0', 'right-top', 'branch', 200, 40),
      node('branch-r-1-1', 'right-bot', 'branch', 200, 120),
      node('branch-l-1-0', 'left-top', 'branch', -200, 40),
      node('branch-l-1-1', 'left-bot', 'branch', -200, 120),
      node('branch-r-2-2', 'child', 'branch', 320, 40),
    ]
    const connections: Connection[] = [
      edge('e0', 'topic', 'branch-r-1-0'),
      edge('e1', 'topic', 'branch-r-1-1'),
      edge('e2', 'topic', 'branch-l-1-0'),
      edge('e3', 'topic', 'branch-l-1-1'),
      edge('e4', 'branch-r-1-0', 'branch-r-2-2'),
    ]
    const map = buildMindMapBranchNumberMap(nodes, connections, 'decimal', 'outline')
    expect(map.has('topic')).toBe(false)
    expect(map.get('branch-r-1-0')).toBe('1.')
    expect(map.get('branch-r-1-1')).toBe('2.')
    expect(map.get('branch-l-1-1')).toBe('3.')
    expect(map.get('branch-l-1-0')).toBe('4.')
    expect(map.get('branch-r-2-2')).toBe('1.1')
  })

  it('uses 前缀 glyph on L1 and restarting glyph on children', () => {
    const nodes: DiagramNode[] = [
      node('topic', 'T', 'topic', 0, 0),
      node('branch-r-1-0', 'A', 'branch', 100, 0),
      node('branch-r-2-1', 'a1', 'branch', 200, 0),
      node('branch-r-2-2', 'a2', 'branch', 200, 40),
    ]
    const connections: Connection[] = [
      edge('e0', 'topic', 'branch-r-1-0'),
      edge('e1', 'branch-r-1-0', 'branch-r-2-1'),
      edge('e2', 'branch-r-1-0', 'branch-r-2-2'),
    ]
    const map = buildMindMapBranchNumberMap(nodes, connections, 'upperAlpha', 'lowerAlpha')
    expect(map.get('branch-r-1-0')).toBe('A.')
    expect(map.get('branch-r-2-1')).toBe('a.')
    expect(map.get('branch-r-2-2')).toBe('b.')
  })

  it('builds a 10-level outline path without a trailing dot', () => {
    const nodes: DiagramNode[] = [node('topic', 'T', 'topic', 0, 0)]
    const connections: Connection[] = []
    let parent = 'topic'
    for (let depth = 1; depth <= 10; depth += 1) {
      const id = `n${depth}`
      nodes.push(node(id, `L${depth}`, 'branch', depth * 80, 0))
      connections.push(edge(`e${depth}`, parent, id))
      parent = id
    }
    const map = buildMindMapBranchNumberMap(nodes, connections, 'decimal', 'outline')
    expect(map.get('n1')).toBe('1.')
    expect(map.get('n2')).toBe('1.1')
    expect(map.get('n10')).toBe('1.1.1.1.1.1.1.1.1.1')
    expect(map.get('n10')?.endsWith('.')).toBe(false)
  })
})

describe('mindMapBranchNumbering text helpers', () => {
  it('joins and strips the current prefix only', () => {
    expect(joinMindMapBranchDisplayText('1.1', 'china')).toBe('1.1 china')
    expect(stripMatchingBranchNumberPrefix('1.1 china', '1.1')).toBe('china')
    expect(stripMatchingBranchNumberPrefix('china', '1.1')).toBe('china')
    expect(stripMatchingBranchNumberPrefix('一、 china', '一、')).toBe('china')
    expect(stripMatchingBranchNumberPrefix('第一章 引言', '第一章')).toBe('引言')
    expect(stripMatchingBranchNumberPrefix('第一条 定义', '第一条')).toBe('定义')
    expect(stripMatchingBranchNumberPrefix('① shanghai', '①')).toBe('shanghai')
  })

  it('resolves defaults and enabled flag', () => {
    expect(isMindMapBranchNumberingEnabled({})).toBe(false)
    expect(isMindMapBranchNumberingEnabled({ _mindmap_branch_numbering: true })).toBe(true)
    expect(resolveMindMapBranchNumberingPrefix('circled')).toBe('circled')
    expect(resolveMindMapBranchNumberingPrefix('nope')).toBe('decimal')
    expect(resolveMindMapBranchNumberingNested('outline')).toBe('outline')
    expect(resolveMindMapBranchNumberingNested('lowerAlpha')).toBe('lowerAlpha')
  })

  it('defaults numbering off unless the source flag is exactly true', () => {
    const data: Record<string, unknown> = {}
    writeMindMapNumberingLiveFields(data, { branch_numbering_prefix: 'chinese' }, data)
    expect(data._mindmap_branch_numbering).toBe(false)
    expect(data._mindmap_branch_numbering_prefix).toBe('chinese')
    writeMindMapNumberingLiveFields(data, { branch_numbering: true, branch_numbering_prefix: 'circled' })
    expect(data._mindmap_branch_numbering).toBe(true)
    writeMindMapNumberingLiveFields(data, { branch_numbering: false })
    expect(data._mindmap_branch_numbering).toBe(false)
  })

  it('rebuilds the cached map when prefix style switches', () => {
    const nodes: DiagramNode[] = [
      node('topic', 'T', 'topic', 0, 0),
      node('branch-r-1-0', 'A', 'branch', 100, 0),
    ]
    const connections: Connection[] = [edge('e0', 'topic', 'branch-r-1-0')]
    const data = {
      _mindmap_branch_numbering: true,
      _mindmap_branch_numbering_prefix: 'decimal',
      _mindmap_branch_numbering_nested: 'outline',
      nodes,
      connections,
    }
    invalidateMindMapBranchNumberMapCache()
    expect(mindMapBranchNumberMapFromData(data).get('branch-r-1-0')).toBe('1.')
    data._mindmap_branch_numbering_prefix = 'chineseChapter'
    expect(mindMapBranchNumberMapFromData(data).get('branch-r-1-0')).toBe('第一章')
  })

  it('sizes the branch box from this prefix glyphs, not a generic allowance', () => {
    const label = '分支1'
    const id = 'branch-r-1-0'
    const chapter = estimateNumberedBranchWidth(label, '第一章', id)
    const decimal = estimateNumberedBranchWidth(label, '1.', id)
    expect(chapter).toBeGreaterThan(decimal)
    expect(estimateNumberedBranchWidth(label, '1.1.1', id)).toBeGreaterThan(decimal)
  })

  it('uses a taller wrap estimate for 第一章 than 1. on a long label', () => {
    const long =
      '这是一段足够长的思维导图分支文字用来触发换行限制检查一二三四五六七八九十'
    const id = 'branch-r-1-0'
    const chapterH = measureNumberedBranchHeight(long, '第一章', id)
    const decimalH = measureNumberedBranchHeight(long, '1.', id)
    expect(chapterH).toBeGreaterThanOrEqual(decimalH)
  })
})
