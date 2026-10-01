import { readFileSync, readdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import {
  abbreviateToolbarLabel,
  toolbarLabelGraphemeLength,
} from '@/utils/toolbarLabelAbbreviation'

const TOOLBAR_LABEL_KEYS = [
  'common.save',
  'canvas.toolbar.import',
  'canvas.toolbar.export',
  'canvas.toolbar.nodeStyleFollow',
  'canvas.toolbar.mindMapAppearanceNumbering',
  'canvas.ribbon.tabFile',
  'canvas.ribbon.tabEdit',
  'canvas.ribbon.tabDraw',
  'canvas.ribbon.tabTeaching',
  'canvas.ribbon.tabResearch',
  'canvas.ribbon.tabInsert',
  'canvas.ribbon.historyVersions',
  'canvas.ribbon.themeStyle',
  'canvas.ribbon.topicGenerate',
  'canvas.ribbon.docGenerate',
  'canvas.ribbon.webGenerate',
  'canvas.ribbon.voiceSummary',
  'canvas.ribbon.makeLearningSheet',
  'canvas.ribbon.mindMate',
  'canvas.mindMapSideToolbar.learningSheet',
  'canvas.mindMapSideToolbar.waterfall',
  'canvas.mindMapSideToolbar.oneSentence',
  'canvas.mindMapSideToolbar.mindClassroom',
  'canvas.floatingToolbar.explain',
  'canvas.floatingToolbar.aiSubgraph',
  'canvas.zoomControls.presentationMode',
]

const COMPOUND_TAIL = ['generierung', 'erstellung', 'generatie', 'generering']
const PARTICLE_TAIL = [
  '으로',
  '에서',
  '에게',
  '을',
  '를',
  '은',
  '는',
  '과',
  '와',
  '의',
  '도',
  '만',
  '이',
  '가',
  '로',
]

const localesRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../src/locales/messages')

function readLocaleStrings(): Array<{ lang: string; key: string; value: string }> {
  const rows: Array<{ lang: string; key: string; value: string }> = []
  const keySet = new Set(TOOLBAR_LABEL_KEYS)
  const pattern = /['"]([^'"]+)['"]\s*:\s*'((?:\\'|[^'])*)'/g
  for (const lang of readdirSync(localesRoot)) {
    if (lang === 'it_test' || lang.endsWith('.ts')) continue
    const dir = resolve(localesRoot, lang)
    let files: string[]
    try {
      files = readdirSync(dir).filter((name) => name.endsWith('.ts'))
    } catch {
      continue
    }
    for (const name of files) {
      const text = readFileSync(resolve(dir, name), 'utf8')
      for (const match of text.matchAll(pattern)) {
        const key = match[1]
        if (!key || !keySet.has(key)) continue
        rows.push({ lang, key, value: match[2].replace(/\\'/g, "'") })
      }
    }
  }
  return rows
}

function fold(word: string): string {
  return word.toLocaleLowerCase('en-US')
}

function visualWidth(text: string): number {
  const graphemes = [
    ...new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(text),
  ].map((part) => part.segment)
  const wide =
    /\p{Script=Thai}|\p{Script=Lao}|\p{Script=Myanmar}|\p{Script=Khmer}|\p{Script=Devanagari}|\p{Script=Bengali}|\p{Script=Gurmukhi}|\p{Script=Tamil}|\p{Script=Telugu}|\p{Script=Kannada}|\p{Script=Malayalam}|\p{Script=Sinhala}|\p{Script=Hangul}|\p{Script=Han}|\p{Script=Hiragana}|\p{Script=Katakana}/u
  return graphemes.reduce((sum, grapheme) => sum + (wide.test(grapheme) ? 2 : 1), 0)
}

function segmenterLocale(text: string): string | undefined {
  if (/[\u0E00-\u0E7F]/u.test(text)) return 'th'
  if (/[\u3040-\u30FF]/u.test(text)) return 'ja'
  if (/[\uAC00-\uD7AF]/u.test(text)) return 'ko'
  if (/[\u0600-\u06FF]/u.test(text)) return 'ar'
  if (/[\u0900-\u097F]/u.test(text)) return 'hi'
  if (/[\u0D80-\u0DFF]/u.test(text)) return 'si'
  if (/[\u0B80-\u0BFF]/u.test(text)) return 'ta'
  if (/[\u3400-\u9FFF]/u.test(text)) return 'zh'
  return undefined
}

function wordTokens(text: string): string[] {
  return [...new Intl.Segmenter(segmenterLocale(text), { granularity: 'word' }).segment(text)]
    .filter((part) => part.isWordLike)
    .map((part) => fold(part.segment))
}

function matchesToken(token: string, piece: string): boolean {
  if (token === piece) return true
  const tail = token.startsWith(piece) ? token.slice(piece.length) : ''
  return COMPOUND_TAIL.includes(tail) || PARTICLE_TAIL.includes(tail)
}

/** A chip piece must be a real word from the label, not an initialism. */
function isWholeWordPiece(value: string, piece: string): boolean {
  const needle = fold(piece)
  if (needle === fold(value)) return true
  const tokens = wordTokens(value)
  if (tokens.some((token) => matchesToken(token, needle))) return true
  for (let index = 0; index < tokens.length - 1; index += 1) {
    const left = tokens[index] ?? ''
    const right = tokens[index + 1] ?? ''
    if (
      needle === `${left}${right}` ||
      needle === `${left}-${right}` ||
      needle === `${left}'${right}` ||
      needle === `${left}’${right}`
    ) {
      return true
    }
  }
  return false
}

describe('abbreviateToolbarLabel', () => {
  it('keeps labels that already name the command', () => {
    expect(abbreviateToolbarLabel('Save')).toBe('Save')
    expect(abbreviateToolbarLabel('Export')).toBe('Export')
    expect(abbreviateToolbarLabel('导出')).toBe('导出')
    expect(abbreviateToolbarLabel('文件')).toBe('文件')
    expect(abbreviateToolbarLabel('历史版本')).toBe('历史版本')
    expect(abbreviateToolbarLabel('MindMate AI')).toBe('MindMate AI')
    expect(abbreviateToolbarLabel('Learning worksheet')).toBe('Learning worksheet')
    expect(abbreviateToolbarLabel('Phiên bản lịch sử')).toBe('Phiên bản lịch sử')
    expect(abbreviateToolbarLabel('Knotenerklärung')).toBe('Knotenerklärung')
  })

  it('keeps a real word from the phrase instead of initials', () => {
    expect(abbreviateToolbarLabel('Web link generation')).toBe('Web link')
    expect(abbreviateToolbarLabel('Generate subgraph with AI')).toBe('subgraph')
    expect(abbreviateToolbarLabel('Dokumentenerstellung')).toBe('Dokumenten')
    expect(abbreviateToolbarLabel('Zusammenfassung der Aufnahme')).toBe('Zusammenfassung')
    expect(abbreviateToolbarLabel('Lehre und Forschung')).toBe('Lehre Forschung')
    expect(abbreviateToolbarLabel('الجيل الذكي من الرسوم البيانية الفرعية')).toBe('الرسوم البيانية')
    expect(abbreviateToolbarLabel('एक स्टडी शीट बनाएं')).toBe('स्टडी शीट')
    expect(abbreviateToolbarLabel('පාඩම් පත්‍රිකාවක් සාදන්න')).toBe('පාඩම්')
    expect(abbreviateToolbarLabel('AI සමඟ උප ප්‍රස්ථාරය ජනනය කරන්න')).toBe('උප ප්‍රස්ථාරය')
    expect(abbreviateToolbarLabel('Ein-Satz-Generierung')).toBe('Satz')
  })

  it('uses a whole word from every shipped toolbar translation', () => {
    const rows = readLocaleStrings()
    const langs = new Set(rows.map((row) => row.lang))
    expect(langs.size).toBeGreaterThanOrEqual(79)
    expect(rows.length).toBeGreaterThan(TOOLBAR_LABEL_KEYS.length * 70)
    for (const row of rows) {
      const short = abbreviateToolbarLabel(row.value)
      const label = `${row.lang} ${row.key} “${row.value}” → “${short}”`
      expect(short.length, label).toBeGreaterThan(0)
      const pieces = short.split(' ')
      if (short !== row.value) {
        for (const piece of pieces) {
          expect(isWholeWordPiece(row.value, piece), label).toBe(true)
        }
      }
      const width = visualWidth(short)
      const singleWord = pieces.length === 1
      expect(singleWord || width <= 18, label).toBe(true)
      if (!singleWord) {
        expect(toolbarLabelGraphemeLength(short), label).toBeLessThanOrEqual(
          toolbarLabelGraphemeLength(row.value)
        )
      }
    }
  })
})
