/**
 * Numbered Kitty clarify options — persist tap chips across history hydrate.
 */
import type {
  OneSentenceChatMessage,
  OneSentenceClarifyChoice,
} from '@/stores/oneSentence'

export const MAX_CLARIFY_CHOICES = 8

const LINE_OPTION_RE = /^\s*(\d+)\s*[)）.、.]\s*(.+?)\s*$/
const INLINE_OPTION_RE = /(\d+)\s*[)）.、.]\s*(.+?)(?=\s+\d+\s*[)）.、.]|$)/g
const CLARIFY_FOOTER_RE =
  /(?:请回复序号或选项内容。?|Reply with the number or option text\.?)\s*$/i

function asConsecutiveChoices(
  rows: Array<{ index: number; label: string }>
): OneSentenceClarifyChoice[] {
  if (rows.length < 2 || rows.length > MAX_CLARIFY_CHOICES) {
    return []
  }
  const choices: OneSentenceClarifyChoice[] = []
  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i]
    const label = row.label.trim()
    if (row.index !== i + 1 || !label) {
      return []
    }
    choices.push({ index: row.index, label })
  }
  return choices
}

function parseLineChoices(text: string): OneSentenceClarifyChoice[] {
  const rows: Array<{ index: number; label: string }> = []
  for (const line of text.split(/\r?\n/)) {
    const match = LINE_OPTION_RE.exec(line)
    if (!match) {
      continue
    }
    rows.push({
      index: Number(match[1]),
      label: match[2],
    })
    if (rows.length >= MAX_CLARIFY_CHOICES) {
      break
    }
  }
  return asConsecutiveChoices(rows)
}

function parseInlineChoices(text: string): OneSentenceClarifyChoice[] {
  const rows: Array<{ index: number; label: string }> = []
  for (const match of text.matchAll(INLINE_OPTION_RE)) {
    rows.push({
      index: Number(match[1]),
      label: match[2],
    })
    if (rows.length >= MAX_CLARIFY_CHOICES) {
      break
    }
  }
  return asConsecutiveChoices(rows)
}

function stripClarifyFooter(text: string): string {
  return text.replace(CLARIFY_FOOTER_RE, '').trim()
}

function stripFooterFromChoices(
  choices: OneSentenceClarifyChoice[]
): OneSentenceClarifyChoice[] {
  if (choices.length === 0) {
    return choices
  }
  const last = choices[choices.length - 1]
  const cleaned = stripClarifyFooter(last.label)
  if (cleaned === last.label || !cleaned) {
    return cleaned ? choices : []
  }
  return [...choices.slice(0, -1), { ...last, label: cleaned }]
}

/** Parse `1) 改主题` / `1. Add a branch` lists from a Kitty reply. */
export function parseNumberedClarifyChoices(text: string): OneSentenceClarifyChoice[] {
  const trimmed = stripClarifyFooter(text.trim())
  if (!trimmed) {
    return []
  }
  const fromLines = stripFooterFromChoices(parseLineChoices(trimmed))
  if (fromLines.length >= 2) {
    return fromLines
  }
  return stripFooterFromChoices(parseInlineChoices(trimmed))
}

export function choicesFromCommandDetail(raw: unknown): OneSentenceClarifyChoice[] {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return []
  }
  return choicesFromClarifyOptions((raw as { clarify_options?: unknown }).clarify_options)
}

export function choicesFromClarifyOptions(raw: unknown): OneSentenceClarifyChoice[] {
  if (!Array.isArray(raw)) {
    return []
  }
  const choices: OneSentenceClarifyChoice[] = []
  for (const item of raw) {
    if (typeof item !== 'string' || !item.trim()) {
      continue
    }
    choices.push({ index: choices.length + 1, label: item.trim() })
    if (choices.length >= MAX_CLARIFY_CHOICES) {
      break
    }
  }
  return choices.length >= 2 ? choices : []
}

export function resolveClarifyChoices(
  explicit: OneSentenceClarifyChoice[] | undefined,
  text: string
): OneSentenceClarifyChoice[] | undefined {
  if (explicit && explicit.length >= 2) {
    return explicit.slice(0, MAX_CLARIFY_CHOICES)
  }
  const parsed = parseNumberedClarifyChoices(text)
  return parsed.length >= 2 ? parsed : undefined
}

function hydrateChoiceKey(row: OneSentenceChatMessage): string {
  const requestId = row.requestId?.trim() ?? ''
  if (requestId) {
    return `${row.role}:${requestId}`
  }
  return `${row.role}:${row.text}`
}

/**
 * Keep live chips when Redis/PG hydrate replaces bubbles (text only).
 * Last Kitty row also re-parses numbered options so a reload still shows taps.
 */
export function applyClarifyChoicesOnHydrate(
  rows: OneSentenceChatMessage[],
  previousRows: OneSentenceChatMessage[] = []
): OneSentenceChatMessage[] {
  const prevByKey = new Map<string, OneSentenceChatMessage>()
  for (const row of previousRows) {
    prevByKey.set(hydrateChoiceKey(row), row)
  }

  const next = rows.map((row) => {
    const prev = prevByKey.get(hydrateChoiceKey(row))
    if (!prev) {
      return row
    }
    if (!prev.choices?.length && prev.choicesConsumed !== true) {
      return row
    }
    return {
      ...row,
      ...(prev.choices?.length ? { choices: prev.choices } : {}),
      ...(prev.choicesConsumed ? { choicesConsumed: true } : {}),
    }
  })

  const last = next[next.length - 1]
  if (last?.role === 'kitty' && !last.choicesConsumed && !last.choices?.length) {
    if (previousOfferAlreadyAnswered(previousRows, last.text)) {
      return next
    }
    const parsed = parseNumberedClarifyChoices(last.text)
    if (parsed.length >= 2) {
      next[next.length - 1] = { ...last, choices: parsed }
    }
  }
  return next
}

function previousOfferAlreadyAnswered(
  previousRows: OneSentenceChatMessage[],
  text: string
): boolean {
  for (let i = previousRows.length - 1; i >= 0; i -= 1) {
    const row = previousRows[i]
    if (row.role !== 'kitty' || row.text !== text) {
      continue
    }
    if (row.choicesConsumed) {
      return true
    }
    return previousRows.slice(i + 1).some((later) => later.role === 'user')
  }
  return false
}

/** Tap targets for a bubble: stored choices, or parse the latest open Kitty offer. */
export function resolveMessageClarifyChoices(
  messages: OneSentenceChatMessage[],
  msg: OneSentenceChatMessage
): OneSentenceClarifyChoice[] {
  if (msg.role !== 'kitty' || msg.choicesConsumed) {
    return []
  }
  if (msg.choices && msg.choices.length >= 2) {
    return msg.choices
  }
  const idx = messages.findIndex((row) => row.id === msg.id)
  if (idx < 0) {
    return []
  }
  if (messages.slice(idx + 1).some((row) => row.role === 'user')) {
    return []
  }
  const lastKitty = [...messages].reverse().find((row) => row.role === 'kitty')
  if (lastKitty?.id !== msg.id) {
    return []
  }
  return parseNumberedClarifyChoices(msg.text)
}
