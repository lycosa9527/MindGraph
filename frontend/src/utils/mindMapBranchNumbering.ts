/**
 * Computed mind-map branch numbering prefixes (not stored in node.text).
 * L1 uses 前缀风格; L2+ uses 下级编号 (outline path or restarting glyph).
 */
import type { Connection, DiagramData, DiagramNode } from '@/types'
import {
  type MindMapOutlineNode,
  buildMindMapOutlineTree,
  mindMapOutlineOrderFingerprint,
} from '@/utils/mindMapOutlineTree'

export const MIND_MAP_NUMBERING_GLYPH_STYLES = [
  'decimal',
  'decimalParen',
  'paren',
  'circled',
  'chinese',
  'chineseParen',
  'chineseChapter',
  'chineseArticle',
  'upperAlpha',
  'lowerAlpha',
  'lowerAlphaParen',
] as const

export type MindMapNumberingGlyphStyle = (typeof MIND_MAP_NUMBERING_GLYPH_STYLES)[number]

export type MindMapNumberingNestedStyle = MindMapNumberingGlyphStyle | 'outline'

export const DEFAULT_MIND_MAP_NUMBERING_PREFIX: MindMapNumberingGlyphStyle = 'decimal'
export const DEFAULT_MIND_MAP_NUMBERING_NESTED: MindMapNumberingNestedStyle = 'outline'

export interface MindMapNumberingStylePreset<
  T extends MindMapNumberingGlyphStyle | 'outline' = MindMapNumberingGlyphStyle | 'outline',
> {
  id: T
  samples: string
}

export const MIND_MAP_NUMBERING_GLYPH_PRESETS: readonly MindMapNumberingStylePreset<MindMapNumberingGlyphStyle>[] =
  [
    { id: 'decimal', samples: '1. 2. 3.' },
    { id: 'decimalParen', samples: '1) 2) 3)' },
    { id: 'paren', samples: '(1) (2) (3)' },
    { id: 'circled', samples: '① ② ③' },
    { id: 'chinese', samples: '一、 二、 三、' },
    { id: 'chineseParen', samples: '(一) (二) (三)' },
    { id: 'chineseChapter', samples: '第一章 第二章 第三章' },
    { id: 'chineseArticle', samples: '第一条 第二条 第三条' },
    { id: 'upperAlpha', samples: 'A. B. C.' },
    { id: 'lowerAlpha', samples: 'a. b. c.' },
    { id: 'lowerAlphaParen', samples: 'a) b) c)' },
  ]

export const MIND_MAP_NUMBERING_NESTED_PRESETS: readonly MindMapNumberingStylePreset<MindMapNumberingNestedStyle>[] =
  [
    { id: 'outline', samples: '1.1 1.2 2.1' },
    { id: 'chineseChapter', samples: '第一章 第一节 第一段' },
    { id: 'chineseArticle', samples: '第一条 第一款 第一项' },
    ...MIND_MAP_NUMBERING_GLYPH_PRESETS.filter(
      (preset) => preset.id !== 'chineseChapter' && preset.id !== 'chineseArticle'
    ),
  ]

const CHINESE_DIGITS = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九'] as const
const CHINESE_CHAPTER_UNITS = ['章', '节', '段', '条', '款', '项'] as const
const CHINESE_ARTICLE_UNITS = ['条', '款', '项', '目'] as const
const CHINESE_DEPTH_STYLES = new Set(['chineseChapter', 'chineseArticle'])
const CIRCLED_1_TO_20 = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'

const GLYPH_STYLE_SET = new Set<string>(MIND_MAP_NUMBERING_GLYPH_STYLES)

export function isMindMapNumberingGlyphStyle(value: unknown): value is MindMapNumberingGlyphStyle {
  return typeof value === 'string' && GLYPH_STYLE_SET.has(value)
}

export function isMindMapNumberingNestedStyle(
  value: unknown
): value is MindMapNumberingNestedStyle {
  return value === 'outline' || isMindMapNumberingGlyphStyle(value)
}

export function isMindMapBranchNumberingEnabled(
  data?: { _mindmap_branch_numbering?: unknown } | null
): boolean {
  return data?._mindmap_branch_numbering === true
}

export function resolveMindMapBranchNumberingPrefix(value: unknown): MindMapNumberingGlyphStyle {
  return isMindMapNumberingGlyphStyle(value) ? value : DEFAULT_MIND_MAP_NUMBERING_PREFIX
}

export function resolveMindMapBranchNumberingNested(value: unknown): MindMapNumberingNestedStyle {
  return isMindMapNumberingNestedStyle(value) ? value : DEFAULT_MIND_MAP_NUMBERING_NESTED
}

export function formatChineseNumber(n: number): string {
  if (!Number.isInteger(n) || n < 1 || n > 99) {
    return String(n)
  }
  if (n < 10) {
    return CHINESE_DIGITS[n] ?? String(n)
  }
  if (n === 10) {
    return '十'
  }
  if (n < 20) {
    return `十${CHINESE_DIGITS[n - 10]}`
  }
  const tens = Math.floor(n / 10)
  const ones = n % 10
  const tensGlyph = CHINESE_DIGITS[tens] ?? String(tens)
  return ones === 0 ? `${tensGlyph}十` : `${tensGlyph}十${CHINESE_DIGITS[ones]}`
}

export function formatCircledNumber(n: number): string {
  if (Number.isInteger(n) && n >= 1 && n <= 20) {
    return CIRCLED_1_TO_20[n - 1] ?? `(${n})`
  }
  return `(${n})`
}

/** 1-based Excel-style letters: 1=A, 26=Z, 27=AA. */
export function formatAlphaNumber(n: number, upper: boolean): string {
  if (!Number.isInteger(n) || n < 1) {
    return String(n)
  }
  const base = upper ? 65 : 97
  let remaining = n
  let out = ''
  while (remaining > 0) {
    remaining -= 1
    out = String.fromCharCode(base + (remaining % 26)) + out
    remaining = Math.floor(remaining / 26)
  }
  return out
}

export function formatMindMapNumberingGlyph(n: number, style: MindMapNumberingGlyphStyle): string {
  switch (style) {
    case 'decimal':
      return `${n}.`
    case 'decimalParen':
      return `${n})`
    case 'paren':
      return `(${n})`
    case 'circled':
      return formatCircledNumber(n)
    case 'chinese':
      return `${formatChineseNumber(n)}、`
    case 'chineseParen':
      return `(${formatChineseNumber(n)})`
    case 'chineseChapter':
      return formatChineseChapterUnit(n, 1)
    case 'chineseArticle':
      return formatChineseArticleUnit(n, 1)
    case 'upperAlpha':
      return `${formatAlphaNumber(n, true)}.`
    case 'lowerAlpha':
      return `${formatAlphaNumber(n, false)}.`
    case 'lowerAlphaParen':
      return `${formatAlphaNumber(n, false)})`
    default:
      return `${n}.`
  }
}

/** ISO 2145 path: dots between levels, no trailing dot. */
export function formatMindMapOutlinePrefix(parts: readonly number[]): string {
  return parts.join('.')
}

/**
 * L1 clockwise index (1-based). ``indexInSide`` is 0-based top→bottom on that side.
 * Right top→bottom, then left bottom→top.
 */
export function mindMapClockwiseL1Index(
  side: 'left' | 'right',
  indexInSide: number,
  rightCount: number,
  leftCount: number
): number {
  if (side === 'right') {
    return indexInSide + 1
  }
  return rightCount + leftCount - indexInSide
}

function formatChineseOrdinalUnit(n: number, units: readonly string[], depth: number): string {
  return `第${formatChineseNumber(n)}${units[depth - 1] ?? '点'}`
}

/** 第N章 / 节 / 段… by 1-based depth (L4+ 条 款 项, then 点). */
export function formatChineseChapterUnit(n: number, depth: number): string {
  return formatChineseOrdinalUnit(n, CHINESE_CHAPTER_UNITS, depth)
}

/** 法律/合同: 第N条 / 款 / 项 / 目, then 点. */
export function formatChineseArticleUnit(n: number, depth: number): string {
  return formatChineseOrdinalUnit(n, CHINESE_ARTICLE_UNITS, depth)
}

export function formatMindMapBranchPrefix(
  parts: readonly number[],
  prefixStyle: MindMapNumberingGlyphStyle,
  nestedStyle: MindMapNumberingNestedStyle
): string {
  if (parts.length === 0) {
    return ''
  }
  if (parts.length === 1) {
    return formatMindMapNumberingGlyph(parts[0] ?? 1, prefixStyle)
  }
  if (nestedStyle === 'outline') {
    return formatMindMapOutlinePrefix(parts)
  }
  if (CHINESE_DEPTH_STYLES.has(nestedStyle)) {
    const index = parts[parts.length - 1] ?? 1
    if (nestedStyle === 'chineseArticle') {
      return formatChineseArticleUnit(index, parts.length)
    }
    return formatChineseChapterUnit(index, parts.length)
  }
  return formatMindMapNumberingGlyph(parts[parts.length - 1] ?? 1, nestedStyle)
}

export function joinMindMapBranchDisplayText(prefix: string, text: string): string {
  if (!prefix) {
    return text
  }
  if (!text) {
    return prefix
  }
  return `${prefix} ${text}`
}

export function stripMatchingBranchNumberPrefix(text: string, prefix: string): string {
  const trimmed = text.trim()
  if (!prefix) {
    return trimmed
  }
  if (trimmed === prefix) {
    return ''
  }
  const withSpace = `${prefix} `
  if (trimmed.startsWith(withSpace)) {
    return trimmed.slice(withSpace.length).trimStart()
  }
  if (trimmed.startsWith(prefix)) {
    const rest = trimmed.slice(prefix.length)
    if (rest === '' || rest.startsWith(' ') || rest.startsWith('\t')) {
      return rest.trimStart()
    }
  }
  return trimmed
}

export function buildMindMapBranchNumberMap(
  nodes: DiagramNode[],
  connections: Connection[],
  prefixStyle: MindMapNumberingGlyphStyle = DEFAULT_MIND_MAP_NUMBERING_PREFIX,
  nestedStyle: MindMapNumberingNestedStyle = DEFAULT_MIND_MAP_NUMBERING_NESTED
): Map<string, string> {
  const map = new Map<string, string>()
  const tree = buildMindMapOutlineTree(nodes, connections)
  const walk = (list: MindMapOutlineNode[], ancestorParts: number[]): void => {
    list.forEach((node, index) => {
      const parts = [...ancestorParts, index + 1]
      map.set(node.id, formatMindMapBranchPrefix(parts, prefixStyle, nestedStyle))
      walk(node.children, parts)
    })
  }
  for (const root of tree) {
    walk(root.children, [])
  }
  return map
}

type NumberingData = {
  _mindmap_branch_numbering?: unknown
  _mindmap_branch_numbering_prefix?: unknown
  _mindmap_branch_numbering_nested?: unknown
  nodes?: DiagramNode[]
  connections?: Connection[]
} | null

export function mindMapBranchNumberPrefixForNode(nodeId: string, data: NumberingData): string {
  if (!isMindMapBranchNumberingEnabled(data) || !data?.nodes?.length) {
    return ''
  }
  const map = buildMindMapBranchNumberMap(
    data.nodes,
    data.connections ?? [],
    resolveMindMapBranchNumberingPrefix(data._mindmap_branch_numbering_prefix),
    resolveMindMapBranchNumberingNested(data._mindmap_branch_numbering_nested)
  )
  return map.get(nodeId) ?? ''
}

export function mindMapBranchMeasureText(
  nodeId: string,
  text: string,
  data: NumberingData
): string {
  return joinMindMapBranchDisplayText(mindMapBranchNumberPrefixForNode(nodeId, data), text)
}

let numberMapCacheKey = ''
let numberMapCache = new Map<string, string>()

function mindMapNumberMapCacheKey(data: NonNullable<NumberingData>): string {
  const enabled = isMindMapBranchNumberingEnabled(data)
  const prefix = resolveMindMapBranchNumberingPrefix(data._mindmap_branch_numbering_prefix)
  const nested = resolveMindMapBranchNumberingNested(data._mindmap_branch_numbering_nested)
  const order = mindMapOutlineOrderFingerprint(data.nodes ?? [], data.connections ?? [])
  return `${enabled}:${prefix}:${nested}:${order}`
}

export function invalidateMindMapBranchNumberMapCache(): void {
  numberMapCacheKey = ''
  numberMapCache = new Map()
}

export function mindMapBranchNumberMapFromData(data: NumberingData): Map<string, string> {
  if (!isMindMapBranchNumberingEnabled(data) || !data?.nodes?.length) {
    return new Map()
  }
  const key = mindMapNumberMapCacheKey(data)
  if (key === numberMapCacheKey) {
    return numberMapCache
  }
  numberMapCache = buildMindMapBranchNumberMap(
    data.nodes,
    data.connections ?? [],
    resolveMindMapBranchNumberingPrefix(data._mindmap_branch_numbering_prefix),
    resolveMindMapBranchNumberingNested(data._mindmap_branch_numbering_nested)
  )
  numberMapCacheKey = key
  return numberMapCache
}

export function applyMindMapNumberingToMeasureText(
  nodeId: string,
  text: string,
  numberMap: Map<string, string> | null | undefined
): string {
  if (!numberMap || numberMap.size === 0) {
    return text
  }
  return joinMindMapBranchDisplayText(numberMap.get(nodeId) ?? '', text)
}

export function numberingFieldsFromDiagramData(
  data: DiagramData | Record<string, unknown> | null | undefined
): {
  enabled: boolean
  prefix: MindMapNumberingGlyphStyle
  nested: MindMapNumberingNestedStyle
} {
  return {
    enabled: isMindMapBranchNumberingEnabled(data),
    prefix: resolveMindMapBranchNumberingPrefix(data?._mindmap_branch_numbering_prefix),
    nested: resolveMindMapBranchNumberingNested(data?._mindmap_branch_numbering_nested),
  }
}

export function deleteMindMapNumberingLiveFields(
  data: Record<string, unknown> | DiagramData
): void {
  delete data._mindmap_branch_numbering
  delete data._mindmap_branch_numbering_prefix
  delete data._mindmap_branch_numbering_nested
}

export function writeMindMapNumberingLiveFields(
  data: Record<string, unknown> | DiagramData,
  source?: {
    branch_numbering?: boolean
    branch_numbering_prefix?: string
    branch_numbering_nested?: string
  } | null,
  fallback?: Record<string, unknown> | DiagramData | null
): void {
  const prefix = source?.branch_numbering_prefix ?? fallback?._mindmap_branch_numbering_prefix
  const nested = source?.branch_numbering_nested ?? fallback?._mindmap_branch_numbering_nested
  if (prefix !== undefined) {
    data._mindmap_branch_numbering_prefix = resolveMindMapBranchNumberingPrefix(prefix)
  }
  if (nested !== undefined) {
    data._mindmap_branch_numbering_nested = resolveMindMapBranchNumberingNested(nested)
  }
  data._mindmap_branch_numbering =
    (source?.branch_numbering ?? fallback?._mindmap_branch_numbering) === true
}
