/**
 * Zulip-style markdown inserts for the 研习社 compose box.
 * Pure string transforms so toolbar actions stay testable.
 */

export type ComposeFormatType =
  | 'bold'
  | 'italic'
  | 'strikethrough'
  | 'code'
  | 'codeBlock'
  | 'link'
  | 'bulleted'
  | 'numbered'
  | 'quote'
  | 'spoiler'
  | 'latex'
  | 'table'

export interface ComposeFormatResult {
  text: string
  start: number
  end: number
}

const PLACEHOLDER = 'text'

function wrapRange(
  text: string,
  start: number,
  end: number,
  before: string,
  after: string,
  placeholder = PLACEHOLDER
): ComposeFormatResult {
  const selected = text.slice(start, end)
  const inner = selected || placeholder
  const replacement = `${before}${inner}${after}`
  const nextStart = start + before.length
  return {
    text: text.slice(0, start) + replacement + text.slice(end),
    start: nextStart,
    end: nextStart + inner.length,
  }
}

function lineSpan(text: string, start: number, end: number): { from: number; to: number } {
  const from = text.lastIndexOf('\n', start - 1) + 1
  const nl = text.indexOf('\n', end)
  return { from, to: nl === -1 ? text.length : nl }
}

function isBulleted(line: string): boolean {
  return /^\s*[-*+]\s+/.test(line)
}

function isNumbered(line: string): boolean {
  return /^\s*\d+\.\s+/.test(line)
}

function stripListMark(line: string): string {
  return line.replace(/^\s*(?:[-*+]\s+|\d+\.\s+)/, '')
}

function formatList(
  text: string,
  start: number,
  end: number,
  kind: 'bulleted' | 'numbered'
): ComposeFormatResult {
  const { from, to } = lineSpan(text, start, end)
  const block = text.slice(from, to)
  const lines = block.length === 0 ? [''] : block.split('\n')
  const marked = lines.every((line) => (kind === 'bulleted' ? isBulleted(line) : isNumbered(line)))
  const nextLines = marked
    ? lines.map((line) => stripListMark(line))
    : lines.map((line, index) => {
        const body = stripListMark(line)
        if (kind === 'bulleted') {
          return `- ${body || PLACEHOLDER}`
        }
        return `${index + 1}. ${body || PLACEHOLDER}`
      })
  const replacement = nextLines.join('\n')
  return {
    text: text.slice(0, from) + replacement + text.slice(to),
    start: from,
    end: from + replacement.length,
  }
}

function wrapFence(
  text: string,
  start: number,
  end: number,
  open: string,
  close: string,
  placeholder: string
): ComposeFormatResult {
  let prefix = open
  let suffix = close
  if (start > 0 && text.charAt(start - 1) !== '\n') {
    prefix = `\n${prefix}`
  }
  if (end < text.length && text.charAt(end) !== '\n') {
    suffix = `${suffix}\n`
  }
  return wrapRange(text, start, end, prefix, suffix, placeholder)
}

function formatLatex(text: string, start: number, end: number): ComposeFormatResult {
  const selected = text.slice(start, end)
  if (selected === '' || selected.includes('\n')) {
    return wrapFence(text, start, end, '```math\n', '\n```', PLACEHOLDER)
  }
  return wrapRange(text, start, end, '$$', '$$', PLACEHOLDER)
}

const TABLE_SNIPPET = '| A | B |\n| --- | --- |\n|  |  |'

function insertTable(text: string, start: number, end: number): ComposeFormatResult {
  let snippet = TABLE_SNIPPET
  if (start > 0 && text.charAt(start - 1) !== '\n') {
    snippet = `\n${snippet}`
  }
  if (end < text.length && text.charAt(end) !== '\n') {
    snippet = `${snippet}\n`
  }
  const next = text.slice(0, start) + snippet + text.slice(end)
  const cell = snippet.indexOf('A')
  const abs = cell === -1 ? start : start + cell
  return { text: next, start: abs, end: abs + 1 }
}

export function applyComposeFormat(
  text: string,
  start: number,
  end: number,
  type: ComposeFormatType
): ComposeFormatResult {
  const lo = Math.max(0, Math.min(start, end, text.length))
  const hi = Math.max(0, Math.min(Math.max(start, end), text.length))
  switch (type) {
    case 'bold':
      return wrapRange(text, lo, hi, '**', '**')
    case 'italic':
      return wrapRange(text, lo, hi, '*', '*')
    case 'strikethrough':
      return wrapRange(text, lo, hi, '~~', '~~')
    case 'code':
      return wrapRange(text, lo, hi, '`', '`')
    case 'codeBlock':
      return wrapFence(text, lo, hi, '```\n', '\n```', PLACEHOLDER)
    case 'link':
      return wrapRange(text, lo, hi, '[', '](url)')
    case 'bulleted':
      return formatList(text, lo, hi, 'bulleted')
    case 'numbered':
      return formatList(text, lo, hi, 'numbered')
    case 'quote':
      return wrapFence(text, lo, hi, '```quote\n', '\n```', PLACEHOLDER)
    case 'spoiler':
      return wrapFence(text, lo, hi, '```spoiler \n', '\n```', PLACEHOLDER)
    case 'latex':
      return formatLatex(text, lo, hi)
    case 'table':
      return insertTable(text, lo, hi)
    default:
      return { text, start: lo, end: hi }
  }
}

export function insertTextAtCursor(
  text: string,
  start: number,
  end: number,
  insert: string
): ComposeFormatResult {
  const lo = Math.max(0, Math.min(start, end, text.length))
  const hi = Math.max(0, Math.min(Math.max(start, end), text.length))
  const next = text.slice(0, lo) + insert + text.slice(hi)
  const caret = lo + insert.length
  return { text: next, start: caret, end: caret }
}
