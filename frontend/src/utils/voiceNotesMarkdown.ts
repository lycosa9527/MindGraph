/**
 * Voice Notes markdown interchange: speaker-prefixed body (human + mindmap)
 * plus a trailing comment with talker slots, remaps, and voiceprint id.
 */
import { DOC_SUMMARY_MAX_INPUT_CHARS } from '@/config/docSummaryApi'
import {
  type VoiceNotesTurn,
  mergeSpeakerSlots,
  parseVoiceNotesTranscript,
  transcriptFromTurns,
} from '@/utils/voiceNotesTranscript'

export const VOICE_NOTES_MD_VERSION = 1
const META_MARKER = 'mg-voice-notes'
const META_BLOCK = /(?:^|\n)<!--\s*mg-voice-notes:1\s*\n([\s\S]*?)\n-->\s*$/
const CONTEXT_ID_MAX = 128

export type VoiceNotesMarkdownDocument = {
  turns: VoiceNotesTurn[]
  speakerNames: Record<number, string>
  speakerIds: number[]
  speakerRemaps: Record<number, number>
  speakerContextId: string
  savedAt: number | null
  elapsedMs: number
}

export function normalizeVoiceNotesContextId(raw: string): string {
  const value = raw.trim()
  if (!value || value.length > CONTEXT_ID_MAX) return ''
  for (const char of value) {
    if (/[A-Za-z0-9._\-:]/.test(char)) continue
    return ''
  }
  return value
}

function asInt(value: unknown): number | null {
  const id = typeof value === 'number' ? value : Number(value)
  return Number.isInteger(id) ? id : null
}

function parseSpeakerIds(raw: unknown): number[] {
  if (!Array.isArray(raw)) return []
  const ids: number[] = []
  for (const value of raw) {
    const id = asInt(value)
    if (id !== null && id >= -1) ids.push(id)
  }
  return ids
}

function parseSlots(raw: unknown): number[] {
  return parseSpeakerIds(raw).filter((id) => id >= 0)
}

function parseNameMap(raw: unknown): Record<number, string> {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
  const names: Record<number, string> = {}
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    const id = asInt(key)
    if (id === null || id < 0 || typeof value !== 'string') continue
    const name = value.replace(/-->/g, '').trim()
    if (name) names[id] = name
  }
  return names
}

function parseRemapMap(raw: unknown): Record<number, number> {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
  const remaps: Record<number, number> = {}
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    const fromId = asInt(key)
    const intoId = asInt(value)
    if (fromId === null || intoId === null || fromId < 0 || intoId < 0 || fromId === intoId) {
      continue
    }
    remaps[fromId] = intoId
  }
  return remaps
}

function parseSavedAt(raw: unknown): number | null {
  const value = asInt(raw)
  return value !== null && value > 0 ? value : null
}

function parseElapsedMs(raw: unknown): number {
  const value = asInt(raw)
  return value !== null && value > 0 ? value : 0
}

export function voiceNotesMarkdownBody(markdown: string): string {
  return splitVoiceNotesMarkdown(markdown).body
}

function splitVoiceNotesMarkdown(markdown: string): { body: string; metaJson: string | null } {
  const text = markdown.replace(/\r\n/g, '\n').trim()
  const matched = META_BLOCK.exec(text)
  if (!matched) return { body: text, metaJson: null }
  return { body: text.slice(0, matched.index).trim(), metaJson: matched[1].trim() }
}

function stringifyMap(values: Record<number, string | number>): Record<string, string | number> {
  const out: Record<string, string | number> = {}
  for (const [key, value] of Object.entries(values)) {
    const id = asInt(key)
    if (id === null || id < 0) continue
    if (typeof value === 'string') {
      const name = value.replace(/-->/g, '').trim()
      if (name) out[String(id)] = name
      continue
    }
    if (Number.isInteger(value) && value >= 0 && value !== id) out[String(id)] = value
  }
  return out
}

function applyTurnIds(turns: VoiceNotesTurn[], ids: number[]): VoiceNotesTurn[] {
  if (ids.length !== turns.length) return turns
  return turns.map((turn, index) =>
    ids[index] === turn.speakerId ? turn : { ...turn, speakerId: ids[index] }
  )
}

export function serializeVoiceNotesMarkdown(input: {
  turns: VoiceNotesTurn[]
  speakerNames: Record<number, string>
  speakerIds: number[]
  speakerRemaps: Record<number, number>
  speakerContextId: string
  savedAt: number
  elapsedMs: number
  labelForSpeakerId: (speakerId: number) => string
  maxChars?: number
}): string {
  const limit = input.maxChars ?? DOC_SUMMARY_MAX_INPUT_CHARS
  let turns = input.turns.filter((turn) => turn.text.trim().length > 0)
  let document = renderVoiceNotesMarkdown(turns, input)
  while (document.length > limit && turns.length > 1) {
    turns = turns.slice(1)
    document = renderVoiceNotesMarkdown(turns, input)
  }
  return document.length > limit ? document.slice(0, limit) : document
}

function renderVoiceNotesMarkdown(
  turns: VoiceNotesTurn[],
  input: {
    speakerNames: Record<number, string>
    speakerIds: number[]
    speakerRemaps: Record<number, number>
    speakerContextId: string
    savedAt: number
    elapsedMs: number
    labelForSpeakerId: (speakerId: number) => string
  }
): string {
  const body = transcriptFromTurns(turns, input.labelForSpeakerId)
  const meta = {
    v: VOICE_NOTES_MD_VERSION,
    ids: turns.map((turn) => turn.speakerId),
    names: stringifyMap(input.speakerNames),
    slots: mergeSpeakerSlots(
      input.speakerIds,
      turns.map((turn) => turn.speakerId)
    ),
    remaps: stringifyMap(input.speakerRemaps),
    ctx: normalizeVoiceNotesContextId(input.speakerContextId),
    saved_at: parseSavedAt(input.savedAt) ?? Date.now(),
    elapsed_ms: parseElapsedMs(input.elapsedMs),
  }
  return `${body}\n\n<!-- ${META_MARKER}:${VOICE_NOTES_MD_VERSION}\n${JSON.stringify(meta)}\n-->`
}

export function parseVoiceNotesMarkdown(
  markdown: string,
  defaultLabelTemplate = '说话人{n}：'
): VoiceNotesMarkdownDocument {
  const { body, metaJson } = splitVoiceNotesMarkdown(markdown)
  const parsed = parseVoiceNotesTranscript(body, defaultLabelTemplate)
  if (!metaJson) {
    const speakerIds = [
      ...new Set(parsed.turns.map((turn) => turn.speakerId).filter((id) => id >= 0)),
    ].sort((left, right) => left - right)
    return {
      turns: parsed.turns,
      speakerNames: parsed.speakerNames,
      speakerIds,
      speakerRemaps: {},
      speakerContextId: '',
      savedAt: null,
      elapsedMs: 0,
    }
  }
  let meta: Record<string, unknown>
  try {
    meta = JSON.parse(metaJson) as Record<string, unknown>
  } catch {
    return parseVoiceNotesMarkdown(body, defaultLabelTemplate)
  }
  if (meta.v !== VOICE_NOTES_MD_VERSION) {
    return parseVoiceNotesMarkdown(body, defaultLabelTemplate)
  }
  const turns = applyTurnIds(parsed.turns, parseSpeakerIds(meta.ids))
  return {
    turns,
    speakerNames: parseNameMap(meta.names),
    speakerIds: mergeSpeakerSlots(
      parseSlots(meta.slots),
      turns.map((turn) => turn.speakerId)
    ),
    speakerRemaps: parseRemapMap(meta.remaps),
    speakerContextId: typeof meta.ctx === 'string' ? normalizeVoiceNotesContextId(meta.ctx) : '',
    savedAt: parseSavedAt(meta.saved_at),
    elapsedMs: parseElapsedMs(meta.elapsed_ms),
  }
}
