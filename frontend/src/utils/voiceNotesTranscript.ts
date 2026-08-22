/**
 * Voice Notes transcript helpers — Tencent ASR V2 snapshot → display lines.
 */

const MAX_COMMITTED_LINES = 500

export type VoiceNotesSnapshotSentence = {
  text?: unknown
  speaker_id?: unknown
  sentence_id?: unknown
  final?: unknown
  sentence_type?: unknown
  start_time?: unknown
}

export type VoiceNotesTurn = {
  speakerId: number
  text: string
  live: boolean
  sentenceId: number
  startTime: number
}

export function formatVoiceNotesSpeakerLine(
  text: string,
  speakerId: unknown,
  speakerLabel: string
): string {
  const line = text.trim()
  if (!line) return ''
  if (!speakerLabel) return line
  const id = typeof speakerId === 'number' ? speakerId : Number(speakerId)
  if (!Number.isInteger(id) || id < 0) return line
  return `${speakerLabel}${line}`
}

export const VOICE_NOTES_MIN_SPEAKER_SLOTS = 3

export function speakerLabelSuffix(template: string): string {
  const token = '{n}'
  const idx = template.indexOf(token)
  if (idx < 0) return '：'
  return template.slice(idx + token.length)
}

export function resolveCustomSpeakerLabel(
  customName: string,
  defaultLabel: string,
  suffix: string
): string {
  const custom = customName.trim()
  if (!custom) return defaultLabel
  if (/[：:]\s*$/.test(custom)) return custom
  return `${custom}${suffix}`
}

export function relabelTranscriptLines(
  rows: string[],
  oldLabel: string,
  newLabel: string
): string[] {
  if (!oldLabel || oldLabel === newLabel) return rows
  return rows.map((line) =>
    line.startsWith(oldLabel) ? `${newLabel}${line.slice(oldLabel.length)}` : line
  )
}

export function collectSnapshotSpeakerIds(sentences: unknown): number[] {
  if (!Array.isArray(sentences)) return []
  const ids = new Set<number>()
  for (const item of sentences) {
    if (!item || typeof item !== 'object') continue
    const raw = (item as VoiceNotesSnapshotSentence).speaker_id
    const id = typeof raw === 'number' ? raw : Number(raw)
    if (Number.isInteger(id) && id >= 0) ids.add(id)
  }
  return [...ids].sort((a, b) => a - b)
}

export function mergeSpeakerSlots(existing: number[], incoming: number[]): number[] {
  const merged = new Set<number>()
  for (let slot = 0; slot < VOICE_NOTES_MIN_SPEAKER_SLOTS; slot += 1) {
    merged.add(slot)
  }
  for (const id of existing) {
    if (Number.isInteger(id) && id >= 0) merged.add(id)
  }
  for (const id of incoming) {
    if (Number.isInteger(id) && id >= 0) merged.add(id)
  }
  return [...merged].sort((a, b) => a - b)
}

export function remapTurnSpeakerIds(
  turns: VoiceNotesTurn[],
  fromId: number,
  intoId: number
): VoiceNotesTurn[] {
  if (fromId === intoId || fromId < 0 || intoId < 0) return turns
  return turns.map((turn) => (turn.speakerId === fromId ? { ...turn, speakerId: intoId } : turn))
}

export function speakerIdsAfterRemoving(existing: number[], removedId: number): number[] {
  return mergeSpeakerSlots(
    existing.filter((id) => id !== removedId),
    []
  )
}

export function defaultSpeakerSlot(speakerId: number): number {
  if (!Number.isInteger(speakerId) || speakerId < 0) return 0
  return speakerId % VOICE_NOTES_MIN_SPEAKER_SLOTS
}

export function resolveSpeakerRemap(speakerId: number, remaps: Record<number, number>): number {
  let current = speakerId
  const seen = new Set<number>()
  while (typeof remaps[current] === 'number' && !seen.has(current)) {
    seen.add(current)
    const next = remaps[current]
    if (!Number.isInteger(next) || next < 0) break
    current = next
  }
  return current
}

export function applySpeakerRemaps(
  turns: VoiceNotesTurn[],
  remaps: Record<number, number>
): VoiceNotesTurn[] {
  if (Object.keys(remaps).length === 0) return turns
  return turns.map((turn) => {
    if (turn.speakerId < 0) return turn
    const mapped = resolveSpeakerRemap(turn.speakerId, remaps)
    return mapped === turn.speakerId ? turn : { ...turn, speakerId: mapped }
  })
}

export function speakerIdsWithRemaps(
  existing: number[],
  incoming: number[],
  remaps: Record<number, number>
): number[] {
  const kept = existing.filter((id) => resolveSpeakerRemap(id, remaps) === id)
  const mappedIncoming = incoming.map((id) => resolveSpeakerRemap(id, remaps))
  return mergeSpeakerSlots(kept, mappedIncoming)
}

export function parseSnapshotSpeakerId(raw: unknown): number {
  const id = typeof raw === 'number' ? raw : Number(raw)
  if (!Number.isInteger(id) || id < 0) return -1
  return id
}

export function parseSnapshotSentenceId(raw: unknown, fallback: number): number {
  const id = typeof raw === 'number' ? raw : Number(raw)
  if (!Number.isInteger(id) || id < 0) return fallback
  return id
}

export function parseSnapshotStartTime(raw: unknown): number {
  const value = typeof raw === 'number' ? raw : Number(raw)
  if (!Number.isFinite(value) || value < 0) return 0
  return value
}

export function joinVoiceNotesSentences(left: string, right: string): string {
  const head = left.trim()
  const tail = right.trim()
  if (!head) return tail
  if (!tail) return head
  if (/[A-Za-z0-9]$/.test(head) && /^[A-Za-z0-9]/.test(tail)) return `${head} ${tail}`
  if (/[.!?]$/.test(head) && /^[A-Za-z]/.test(tail)) return `${head} ${tail}`
  return `${head}${tail}`
}

export function turnsFromSnapshot(sentences: unknown): VoiceNotesTurn[] {
  if (!Array.isArray(sentences)) return []
  const turns: VoiceNotesTurn[] = []
  for (const item of sentences) {
    if (!item || typeof item !== 'object') continue
    const rec = item as VoiceNotesSnapshotSentence
    const text = String(rec.text ?? '').trim()
    if (!text) continue
    const speakerId = parseSnapshotSpeakerId(rec.speaker_id)
    const isFinal = rec.final === true || rec.sentence_type === 1
    turns.push({
      speakerId,
      text,
      live: !isFinal,
      sentenceId: parseSnapshotSentenceId(rec.sentence_id, turns.length),
      startTime: parseSnapshotStartTime(rec.start_time),
    })
  }
  if (turns.length <= MAX_COMMITTED_LINES) return turns
  return turns.slice(-MAX_COMMITTED_LINES)
}

export function remainingVoiceNotesDurationMs(elapsedMs: number, maxMs: number): number {
  if (!Number.isFinite(elapsedMs) || elapsedMs <= 0) return maxMs
  return Math.max(1000, maxMs - elapsedMs)
}

export function mergeCaptureSnapshotTurns(
  committed: VoiceNotesTurn[],
  incoming: VoiceNotesTurn[]
): VoiceNotesTurn[] {
  return coalesceConsecutiveSpeakerTurns([...committed, ...incoming])
}

export function coalesceConsecutiveSpeakerTurns(turns: VoiceNotesTurn[]): VoiceNotesTurn[] {
  const merged: VoiceNotesTurn[] = []
  for (const turn of turns) {
    const last = merged[merged.length - 1]
    if (last && last.speakerId === turn.speakerId && last.speakerId >= 0) {
      merged[merged.length - 1] = {
        speakerId: last.speakerId,
        text: joinVoiceNotesSentences(last.text, turn.text),
        live: last.live || turn.live,
        sentenceId: turn.sentenceId,
        startTime: last.startTime,
      }
      continue
    }
    merged.push(turn)
  }
  if (merged.length <= MAX_COMMITTED_LINES) return merged
  return merged.slice(-MAX_COMMITTED_LINES)
}

export function formatTurnLine(turn: VoiceNotesTurn, speakerLabel: string): string {
  return formatVoiceNotesSpeakerLine(turn.text, turn.speakerId, speakerLabel)
}

export function transcriptFromTurns(
  turns: VoiceNotesTurn[],
  labelForSpeakerId: (speakerId: number) => string
): string {
  return turns
    .map((turn) =>
      formatTurnLine(turn, turn.speakerId >= 0 ? labelForSpeakerId(turn.speakerId) : '')
    )
    .filter((line) => line.length > 0)
    .join('\n')
}

export function commitLiveTurns(turns: VoiceNotesTurn[]): VoiceNotesTurn[] {
  return turns.map((turn) => (turn.live ? { ...turn, live: false } : turn))
}

export function speakerDisplayName(label: string): string {
  return label.replace(/[：:]\s*$/, '').trim()
}

const CJK_CHAR = /\p{Script=Han}|\p{Script=Hiragana}|\p{Script=Katakana}|\p{Script=Hangul}/u
const LETTER_CHAR = /\p{L}/u

export function speakerAvatarGlyph(customName: string, fallbackSlot: number): string {
  const slot = Number.isInteger(fallbackSlot) && fallbackSlot > 0 ? String(fallbackSlot) : '·'
  const trimmed = speakerDisplayName(customName)
  if (!trimmed) return slot
  const letter = trimmed.match(LETTER_CHAR)?.[0]
  if (!letter) return slot
  if (CJK_CHAR.test(letter)) return letter
  return letter.toLocaleUpperCase()
}

export function isVoiceNotesMarkdownFenceLine(line: string): boolean {
  return (
    line.startsWith('<!--') ||
    line === '-->' ||
    line.startsWith('{') ||
    line.startsWith('}') ||
    line.startsWith('"')
  )
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function defaultSpeakerLabelPatterns(template: string): RegExp[] {
  const patterns = [/^说话人(\d+)[：:]/, /^Speaker (\d+):\s*/i]
  const token = '{n}'
  const idx = template.indexOf(token)
  if (idx < 0) return patterns
  const prefix = template.slice(0, idx)
  const suffix = template.slice(idx + token.length)
  if (!prefix && !suffix) return patterns
  return [new RegExp(`^${escapeRegExp(prefix)}(\\d+)${escapeRegExp(suffix)}`), ...patterns]
}

function matchDefaultSpeakerLabel(
  line: string,
  patterns: RegExp[]
): { id: number; text: string } | null {
  for (const pattern of patterns) {
    const matched = pattern.exec(line)
    if (!matched) continue
    const id = Number(matched[1]) - 1
    if (!Number.isInteger(id) || id < 0) continue
    return { id, text: line.slice(matched[0].length).trim() }
  }
  return null
}

export function parseVoiceNotesTranscript(
  markdown: string,
  defaultLabelTemplate = '说话人{n}：'
): { turns: VoiceNotesTurn[]; speakerNames: Record<number, string> } {
  const patterns = defaultSpeakerLabelPatterns(defaultLabelTemplate)
  const reserved = new Set<number>()
  const nameToId = new Map<string, number>()
  const speakerNames: Record<number, string> = {}
  const turns: VoiceNotesTurn[] = []
  const lines = markdown.replace(/\r\n/g, '\n').split('\n')

  for (const raw of lines) {
    const line = raw.trim()
    if (!line || isVoiceNotesMarkdownFenceLine(line)) continue
    const numbered = matchDefaultSpeakerLabel(line, patterns)
    if (numbered) {
      reserved.add(numbered.id)
      if (!numbered.text) continue
      turns.push({
        speakerId: numbered.id,
        text: numbered.text,
        live: false,
        sentenceId: turns.length,
        startTime: turns.length * 10,
      })
      continue
    }
    const custom = /^(.+?)[：:]\s*(.*)$/.exec(line)
    if (!custom) {
      turns.push({
        speakerId: -1,
        text: line,
        live: false,
        sentenceId: turns.length,
        startTime: turns.length * 10,
      })
      continue
    }
    const name = custom[1].trim()
    const text = custom[2].trim()
    if (!name || !text) continue
    let speakerId = nameToId.get(name)
    if (speakerId === undefined) {
      speakerId = 0
      while (reserved.has(speakerId)) speakerId += 1
      nameToId.set(name, speakerId)
      reserved.add(speakerId)
      speakerNames[speakerId] = name
    }
    turns.push({
      speakerId,
      text,
      live: false,
      sentenceId: turns.length,
      startTime: turns.length * 10,
    })
  }

  return { turns, speakerNames }
}

export const VOICE_NOTES_EDITOR_MIN_PX = 36

export function fitVoiceNotesTextarea(el: HTMLTextAreaElement): void {
  el.style.height = '0px'
  el.style.height = `${Math.max(el.scrollHeight, VOICE_NOTES_EDITOR_MIN_PX)}px`
}

export function linesFromEditedTranscript(text: string): string[] {
  const normalized = text.replace(/\r\n/g, '\n')
  const next = normalized.split('\n')
  if (next.length <= MAX_COMMITTED_LINES) return next
  return next.slice(-MAX_COMMITTED_LINES)
}

export function splitVoiceNotesSnapshot(
  sentences: unknown,
  labelForSpeaker: (n: number) => string
): { committed: string[]; live: string } {
  const turns = turnsFromSnapshot(sentences)
  const committed: string[] = []
  let live = ''
  for (const turn of turns) {
    const label = turn.speakerId >= 0 ? labelForSpeaker(turn.speakerId + 1) : ''
    const formatted = formatTurnLine(turn, label)
    if (!formatted) continue
    if (turn.live) live = formatted
    else committed.push(formatted)
  }
  return { committed, live }
}

const VOICE_NOTES_ERROR_I18N: Record<string, string> = {
  tencent_auth: 'auth.voiceNotes.tencentAuth',
  tencent_service: 'auth.voiceNotes.tencentService',
  tencent_quota: 'auth.voiceNotes.tencentQuota',
  tencent_arrears: 'auth.voiceNotes.tencentArrears',
  tencent_concurrency: 'auth.voiceNotes.tencentConcurrency',
  tencent_rps: 'auth.voiceNotes.rateLimited',
  tencent_audio: 'auth.voiceNotes.tencentAudio',
  tencent_send_rate: 'auth.voiceNotes.tencentSendRate',
  tencent_idle: 'auth.voiceNotes.tencentIdle',
  tencent_retry: 'auth.voiceNotes.tencentRetry',
  tencent_region: 'auth.voiceNotes.tencentRegion',
  tencent_param: 'auth.voiceNotes.tencentParam',
  tencent_appid: 'auth.voiceNotes.tencentAppid',
  rate_limit: 'auth.voiceNotes.rateLimited',
  too_large: 'auth.voiceNotes.messageTooLarge',
  invalid_json: 'auth.voiceNotes.invalidMessage',
  bad_start: 'auth.voiceNotes.invalidMessage',
  asr_config: 'auth.voiceNotes.asrUnavailable',
  relay: 'auth.voiceNotes.wsError',
  upstream: 'auth.voiceNotes.wsClosed',
}

export function voiceNotesErrorI18nKey(code: string): string | null {
  return VOICE_NOTES_ERROR_I18N[code] ?? null
}

export function shouldStopVoiceNotesOnServerError(code: string): boolean {
  return (
    code === 'asr_config' ||
    code === 'upstream' ||
    code === 'relay' ||
    code === 'rate_limit' ||
    code === 'too_large' ||
    code === 'invalid_json' ||
    code === 'bad_start' ||
    code.startsWith('tencent_')
  )
}
