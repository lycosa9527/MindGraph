/**
 * Pure helpers for the mobile Voice Notes page: ingest happens on stop;
 * mindmap generation is explicit (Generate button).
 */
import type { VoiceNotesStopReason } from '@/stores/voiceNotes'

const SKIP_GENERATE_REASONS: ReadonlySet<VoiceNotesStopReason> = new Set(['pagehide', 'exit'])

export function shouldGenerateMindmapAfterVoiceStop(input: {
  lastStopReason: VoiceNotesStopReason | null
  transcript: string
  packageId: number | null
  diagramId: string | null
}): boolean {
  if (input.lastStopReason && SKIP_GENERATE_REASONS.has(input.lastStopReason)) {
    return false
  }
  if (!input.packageId || !input.diagramId) {
    return false
  }
  return input.transcript.trim().length > 0
}

export function shouldWarnEmptyVoiceTranscript(input: {
  lastStopReason: VoiceNotesStopReason | null
  transcript: string
}): boolean {
  if (input.transcript.trim().length > 0) {
    return false
  }
  return input.lastStopReason === 'user'
}

export function isMobileAppPath(currentPath: string): boolean {
  return currentPath === '/m' || currentPath.startsWith('/m/')
}

export function resolveVoiceNotesCanvasPath(currentPath: string): string {
  return isMobileAppPath(currentPath) ? '/m/canvas' : '/canvas'
}

export const VOICE_NOTE_TITLE_PREFIX = 'voice recording_'
export const VOICE_NOTES_SOURCE_CHANNEL = 'voice_notes'

export const VOICE_NOTES_STATUS_LINES = [
  'waiting',
  'connectingAsr',
  'recordingAndSeparating',
  'paused',
  'stopping',
  'savingTranscript',
  'generating',
  'ready',
] as const

export type VoiceNotesStatusLine = (typeof VOICE_NOTES_STATUS_LINES)[number]

export type VoiceNotesActionFlags = {
  canStart: boolean
  canPause: boolean
  canResume: boolean
  canStop: boolean
  canCopy: boolean
  canJump: boolean
  canGenerate: boolean
}

export function voiceNotesStatusMessageKey(line: VoiceNotesStatusLine): string {
  return `auth.voiceNotes.status.${line}`
}

export function resolveVoiceNotesStatusLine(input: {
  generating: boolean
  persisting: boolean
  sessionStatus: string
  hasTranscript: boolean
}): VoiceNotesStatusLine {
  if (input.generating) {
    return 'generating'
  }
  if (input.persisting || input.sessionStatus === 'ingesting') {
    return 'savingTranscript'
  }
  if (input.sessionStatus === 'stopping') {
    return 'stopping'
  }
  if (input.sessionStatus === 'connecting' || input.sessionStatus === 'starting') {
    return 'connectingAsr'
  }
  if (input.sessionStatus === 'paused') {
    return 'paused'
  }
  if (input.sessionStatus === 'recording') {
    return 'recordingAndSeparating'
  }
  return input.hasTranscript ? 'ready' : 'waiting'
}

export function resolveVoiceNotesActions(input: {
  recording: boolean
  paused: boolean
  connecting: boolean
  sessionReady: boolean
  stopping: boolean
  ingesting: boolean
  bootstrapping: boolean
  generating?: boolean
  persisting?: boolean
  hasTranscript: boolean
  hasActiveCapture: boolean
}): VoiceNotesActionFlags {
  const pipelineBusy =
    input.stopping || input.ingesting || Boolean(input.generating) || Boolean(input.persisting)
  const handshake = input.connecting || (input.recording && !input.sessionReady && !input.paused)
  return {
    canStart: !input.recording && !input.paused && !handshake && !pipelineBusy,
    canPause: input.recording && input.sessionReady && !input.paused && !pipelineBusy,
    canResume: input.recording && input.paused && !pipelineBusy,
    canStop: (input.recording || input.paused) && !input.stopping && !input.ingesting,
    canCopy: input.hasTranscript,
    canJump: !input.bootstrapping && !pipelineBusy,
    canGenerate: !pipelineBusy && !handshake && (input.hasActiveCapture || input.hasTranscript),
  }
}

export function voiceNotesHistoryListUrl(page: number, pageSize: number): string {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    source_channel: VOICE_NOTES_SOURCE_CHANNEL,
  })
  return `/api/diagrams?${params.toString()}`
}

export function formatVoiceNoteHistoryTitle(title: string): string {
  const trimmed = title.trim()
  if (!trimmed.toLowerCase().startsWith(VOICE_NOTE_TITLE_PREFIX)) {
    return trimmed
  }
  const stamp = trimmed.slice(VOICE_NOTE_TITLE_PREFIX.length)
  if (!/^\d{12}$/.test(stamp)) {
    return trimmed
  }
  const year = Number(stamp.slice(0, 4))
  const month = Number(stamp.slice(4, 6))
  const day = Number(stamp.slice(6, 8))
  const hour = Number(stamp.slice(8, 10))
  const minute = Number(stamp.slice(10, 12))
  const parsed = new Date(year, month - 1, day, hour, minute)
  if (Number.isNaN(parsed.getTime())) {
    return trimmed
  }
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${year}-${pad(month)}-${pad(day)} ${pad(hour)}:${pad(minute)}`
}
